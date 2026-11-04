#!/usr/bin/env python3
"""
Gera os mapas offline do i30 Launcher (um grafo GraphHopper por UF) + manifest.json.

Etapas (cada uma pode ser rodada sozinha com --etapa):
  1. poly      -> polígonos .poly de cada UF (limites IBGE do app + margem de ~3 km p/ não cortar a estrada na divisa)
  2. recorte   -> osmium extract (uma passada no pbf do Brasil, 27 saídas)
  3. divisas   -> "gateways": pontos onde rodovias principais cruzam a divisa entre duas UFs
  4. grafos    -> Importer (GraphHopper 11.1, perfil car + conversões + CH — o MESMO código do app)
  5. pacotes   -> <UF>-<versão>.ghz (zip da pasta do grafo) + sha256 + manifest.json

Não publica nada: só escreve em --saida. Quem publica é o workflow .github/workflows/mapas.yml.
Requer: python3 com shapely>=2 e osmium (pyosmium), osmium-tool, Java 17.
"""
import argparse, datetime, hashlib, json, math, os, shutil, subprocess, sys, zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
# cópia de app/src/main/assets/uf_limites.txt (IBGE, dados abertos)
LIMITES = Path(os.environ.get("MAPAS_LIMITES", AQUI / "uf_limites.txt"))
FORMATO = 1          # MapManifest.FORMAT no app
GH_VERSAO = "11.1"
MARGEM_GRAUS = 0.03  # ~3 km
CLASSES = {"motorway": 0, "trunk": 1, "primary": 2, "secondary": 3, "motorway_link": 4, "trunk_link": 4}
MAX_GATEWAYS = 12
DIST_MIN_KM = 15.0


def log(*a):
    print(datetime.datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def carregar_limites():
    from shapely.geometry import Polygon, MultiPolygon
    ufs = {}
    for linha in LIMITES.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.startswith("#"):
            continue
        uf, aneis = linha.split(";", 1)
        polys = []
        for anel in aneis.split("|"):
            pts = [tuple(map(float, p.split(","))) for p in anel.split()]
            if len(pts) >= 3:
                polys.append(Polygon(pts).buffer(0))
        ufs[uf] = MultiPolygon([g for p in polys for g in (p.geoms if hasattr(p, "geoms") else [p])]).buffer(0)
    assert len(ufs) == 27, f"esperava 27 UFs, achei {len(ufs)}"
    return ufs


def etapa_poly(ufs, trab):
    d = trab / "poly"; d.mkdir(parents=True, exist_ok=True)
    cfg = {"directory": str(trab / "pbf"), "extracts": []}
    for uf, g in ufs.items():
        g2 = g.buffer(MARGEM_GRAUS).simplify(0.002)
        partes = list(g2.geoms) if hasattr(g2, "geoms") else [g2]
        out = [uf]
        for i, p in enumerate(partes, 1):
            out.append(str(i))
            out += [f"   {x:.6f}   {y:.6f}" for x, y in p.exterior.coords]
            out.append("END")
        out.append("END")
        (d / f"{uf}.poly").write_text("\n".join(out) + "\n")
        cfg["extracts"].append({"output": f"{uf}.osm.pbf", "polygon": {"file_name": str(d / f"{uf}.poly"), "file_type": "poly"}})
    (trab / "recortes.json").write_text(json.dumps(cfg, indent=1))
    log("poly ok:", len(ufs), "UFs")


def etapa_recorte(trab, pbf):
    (trab / "pbf").mkdir(parents=True, exist_ok=True)
    subprocess.run(["osmium", "extract", "-v", "--overwrite", "-s", "smart", "-c", str(trab / "recortes.json"), str(pbf)], check=True)
    log("recorte ok")


def etapa_divisas(ufs, trab, pbf):
    """Percorre as rodovias principais; onde dois nós seguidos caem em UFs diferentes, guarda o ponto médio."""
    import numpy as np, osmium, shapely
    from shapely.strtree import STRtree
    nomes = list(ufs)
    geoms = [ufs[u] for u in nomes]
    for g in geoms:
        shapely.prepare(g)
    # faixa de 5 km de cada lado das divisas: só esses nós precisam de teste caro
    faixa = shapely.union_all([g.boundary for g in geoms]).buffer(0.05)
    shapely.prepare(faixa)
    tree = STRtree(geoms)
    achados = {}

    class H(osmium.SimpleHandler):
        def way(self, w):
            cls = CLASSES.get(w.tags.get("highway"))
            if cls is None:
                return
            try:
                xy = np.array([(n.lon, n.lat) for n in w.nodes])
            except osmium.InvalidLocationError:
                return
            if len(xy) < 2:
                return
            na_faixa = shapely.contains_xy(faixa, xy[:, 0], xy[:, 1])
            if not na_faixa.any():
                return
            uf = [None] * len(xy)
            for i in np.nonzero(na_faixa)[0]:
                for j in tree.query(shapely.Point(xy[i]), predicate="intersects"):
                    uf[i] = nomes[j]; break
            for i in range(len(xy) - 1):
                a, b = uf[i], uf[i + 1]
                if a and b and a != b:
                    k = "-".join(sorted((a, b)))
                    achados.setdefault(k, []).append((cls, (xy[i][1] + xy[i + 1][1]) / 2, (xy[i][0] + xy[i + 1][0]) / 2))

    H().apply_file(str(pbf), locations=True, idx="sparse_file_array," + str(trab / "nodes.idx"))
    (trab / "nodes.idx").unlink(missing_ok=True)

    def km(a, b):
        dy = (a[0] - b[0]) * 111.2
        dx = (a[1] - b[1]) * 111.2 * math.cos(math.radians((a[0] + b[0]) / 2))
        return math.hypot(dx, dy)

    gw = {}
    for k, pts in sorted(achados.items()):
        pts.sort(key=lambda p: p[0])  # rodovias maiores primeiro
        esc = []
        for cls, lat, lon in pts:
            if all(km((lat, lon), e) >= DIST_MIN_KM for e in esc):
                esc.append((round(lat, 5), round(lon, 5)))
            if len(esc) >= MAX_GATEWAYS:
                break
        gw[k] = [list(p) for p in esc]
    (trab / "gateways.json").write_text(json.dumps(gw, indent=1))
    log("divisas ok:", len(gw), "pares de UFs,", sum(map(len, gw.values())), "pontos")


def etapa_grafos(trab, ufs_sel, java_opts):
    imp = RAIZ / "importer"
    gradlew = RAIZ / "gradlew"
    subprocess.run([str(gradlew), "-p", str(imp), "-q", "installDist"], check=True)
    binario = imp / "build/install/mapas-importer/bin/mapas-importer"
    for uf in ufs_sel:
        dest = trab / "grafos" / uf
        shutil.rmtree(dest, ignore_errors=True)
        log("importando", uf)
        subprocess.run([str(binario), str(trab / "pbf" / f"{uf}.osm.pbf"), str(dest)], check=True,
                       env={**os.environ, "JAVA_OPTS": java_opts})


def sha256(f):
    h = hashlib.sha256()
    with open(f, "rb") as s:
        for b in iter(lambda: s.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def etapa_pacotes(trab, saida, ufs_sel, versao, url_prefixo):
    saida.mkdir(parents=True, exist_ok=True)
    estados = {}
    for uf in ufs_sel:
        g = trab / "grafos" / uf
        assert (g / "properties").is_file(), f"grafo de {uf} incompleto"
        nome = f"{uf}-{versao}.ghz"
        z = saida / nome
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for f in sorted(g.iterdir()):
                if f.is_file():
                    zf.write(f, f.name)
        inst = sum(f.stat().st_size for f in g.iterdir() if f.is_file())
        estados[uf] = {"url": (url_prefixo.rstrip("/") + "/" + nome) if url_prefixo else nome,
                       "size": z.stat().st_size, "sha256": sha256(z), "installed": inst}
        log(f"{uf}: {z.stat().st_size/1e6:.0f} MB para baixar, {inst/1e6:.0f} MB instalado")
    gw_f = trab / "gateways.json"
    manifest = {"format": FORMATO, "version": versao, "graphhopper": GH_VERSAO,
                "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "attribution": "© colaboradores do OpenStreetMap (ODbL) · GraphHopper (Apache 2.0)",
                "states": estados,
                "gateways": json.loads(gw_f.read_text()) if gw_f.exists() else {}}
    (saida / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    log("manifest ok:", len(estados), "UFs, total", f"{sum(e['size'] for e in estados.values())/1e9:.2f} GB")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pbf", type=Path, required=True, help="brazil-latest.osm.pbf (Geofabrik)")
    ap.add_argument("--trabalho", type=Path, default=Path("trabalho"))
    ap.add_argument("--saida", type=Path, default=Path("saida"))
    ap.add_argument("--versao", default=datetime.date.today().strftime("%Y.%m"), help="AAAA.MM")
    ap.add_argument("--ufs", default="", help="lista separada por vírgula (padrão: todas)")
    ap.add_argument("--url-prefixo", default="", help="ex.: https://github.com/DONO/REPO/releases/download/mapas-2026.11")
    ap.add_argument("--etapa", choices=["poly", "recorte", "divisas", "grafos", "pacotes", "tudo"], default="tudo")
    ap.add_argument("--java-opts", default="-Xmx6g")
    a = ap.parse_args()
    import re
    if not re.fullmatch(r"\d{4}\.\d{2}", a.versao):
        sys.exit("versão deve ser AAAA.MM")
    t = a.trabalho
    e = a.etapa
    sel = [u.strip().upper() for u in a.ufs.split(",") if u.strip()]
    ufs = carregar_limites() if (e in ("poly", "divisas", "tudo") or not sel) else {}
    sel = sel or sorted(ufs)
    if e in ("poly", "tudo"): etapa_poly(ufs, t)
    if e in ("recorte", "tudo"): etapa_recorte(t, a.pbf)
    if e in ("divisas", "tudo"): etapa_divisas(ufs, t, a.pbf)
    if e in ("grafos", "tudo"): etapa_grafos(t, sel, a.java_opts)
    if e in ("pacotes", "tudo"): etapa_pacotes(t, a.saida, sel, a.versao, a.url_prefixo)


if __name__ == "__main__":
    main()
