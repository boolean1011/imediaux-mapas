#!/usr/bin/env python3
"""Junta os manifestos parciais (um por UF, gerados no job da matriz) + gateways.json num manifest.json único.
Falha (exit 1) se faltar alguma UF esperada — assim o workflow nunca publica um latest incompleto."""
import argparse, datetime, json, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--partes", type=Path, required=True)
ap.add_argument("--gateways", type=Path, required=True)
ap.add_argument("--versao", required=True)
ap.add_argument("--esperadas", required=True, help="UFs separadas por vírgula")
ap.add_argument("--saida", type=Path, required=True)
a = ap.parse_args()

estados = {}
for f in sorted(a.partes.rglob("manifest.json")):
    m = json.loads(f.read_text())
    assert m["version"] == a.versao, f"{f}: versão {m['version']} != {a.versao}"
    estados.update(m["states"])
esperadas = sorted(u for u in a.esperadas.split(",") if u)
faltam = sorted(set(esperadas) - set(estados))
if faltam:
    sys.exit(f"faltam UFs no manifest: {','.join(faltam)}")
gw = json.loads(a.gateways.read_text())
manifest = {"format": 1, "version": a.versao, "graphhopper": "11.1",
            "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "attribution": "© colaboradores do OpenStreetMap (ODbL) · GraphHopper (Apache 2.0)",
            "states": {u: estados[u] for u in sorted(estados)},
            "gateways": gw}
a.saida.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
tb = sum(e["size"] for e in estados.values()); ti = sum(e["installed"] for e in estados.values())
print(f"manifest ok: {len(estados)} UFs, {len(gw)} pares de divisa, download {tb/1e9:.2f} GB, instalado {ti/1e9:.2f} GB")
