# imediaux-mapas

Grafos de rota offline (GraphHopper) baixados pelo app iMediaUX Car — um arquivo por UF (27) + `manifest.json`.

O app lê `https://github.com/boolean1011/imediaux-mapas/releases/latest/download/manifest.json`
(formato 1; `url` relativa resolve contra essa mesma pasta).

## Geração automática (grátis, GitHub Actions)

Workflow `.github/workflows/mapas.yml` — todo dia 5, 06:00 UTC, ou manual (Actions → "Mapas mensais (27 UFs)" → Run workflow).

1. **preparar** — baixa `brazil-latest.osm.pbf` da Geofabrik (confere md5), gera os polígonos das UFs
   (limites IBGE + ~3 km de margem), recorta com `osmium extract -s smart` e calcula as divisas (gateways) entre UFs.
2. **grafo** — matriz de 27 jobs paralelos: importa com GraphHopper 11.1 (perfil car, restrições de conversão, CH —
   mesmo `CarProfile`/`CarWeightingFactory` do app), verifica uma rota na capital, empacota `<UF>-AAAA.MM.ghz` + `.sha256`
   e anexa a uma release em **rascunho**.
3. **publicar** — só roda se as 27 UFs deram certo: monta o `manifest.json` (27 UFs + divisas), confere os anexos
   e só então publica a release como **latest**. Se alguma UF falhar, nada muda no latest (fica só o rascunho).

Tag da release: `AAAA.MM` (ou `AAAA.MM-rN` se já existir uma publicada no mês). A versão no manifest é sempre `AAAA.MM`.
Rodada manual com UFs específicas serve para teste e nunca vira latest.

Estrutura: `tools/build_mapas.py` (poly, recorte, divisas, pacotes), `tools/montar_manifest.py`, `tools/uf_limites.txt`
(cópia do app), `tools/capitais.json`, `importer/` (Java 17 + GraphHopper 11.1). `importer/.../nav/gh/*.java` são cópias
dos arquivos do app e precisam ficar idênticas a eles.

## Atribuição e licenças

- Dados de mapa © colaboradores do OpenStreetMap, disponíveis sob a Open Database License (ODbL) 1.0 —
  https://www.openstreetmap.org/copyright · https://opendatacommons.org/licenses/odbl/1-0/
  Os arquivos `.ghz` são bancos de dados derivados do OSM e seguem a ODbL.
- Grafos gerados com GraphHopper 11.1 (Apache License 2.0) — https://github.com/graphhopper/graphhopper
- Extrato do OSM: Geofabrik GmbH (https://download.geofabrik.de). Limites das UFs: IBGE (dados abertos).

Sem dados pessoais.
