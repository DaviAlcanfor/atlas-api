# 034 — "Acontecendo agora": terremotos e eventos naturais
Status: in progress (aprovada pelo dono em 2026-11-17: "planeja como fazer o resto e dale", onda 3 do `atlas-web/specs/PLAN.md`) |
Contrato: CR-015 | Web: atlas-web/specs/034-live-events.md (espelho a criar; notas em "Web" abaixo) | Backlog: B11 (amplia 008)

## Por quê
Pontos pulsando no globo com o que está acontecendo agora: terremotos, incêndios, tempestades, vulcões. As notícias (008)
já existem; esta spec cobre os eventos naturais. Wikipedia "Current events" fica de fora (texto CC BY-SA a resumir; outra spec).

## Dados (licenças lidas em 2026-11-17, antes do código)
- **USGS Earthquake Hazards Program**, feed GeoJSON "M4.5+ Earthquakes, Past Week"
  (`https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson`; a página do feed diz "Updated every minute").
  Licença (https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits): "USGS-authored or produced data
  and information are considered to be in the U.S. Public Domain." Pedido: "When using information from USGS information
  products, publications, or websites, we ask that proper credit be given." Crédito sugerido: "U.S. Geological Survey".
- **NASA EONET v3** (`https://eonet.gsfc.nasa.gov/api/v3/categories/{categoria}?days=7`). Não há licença própria na
  documentação. Diretriz de mídia da NASA (https://www.nasa.gov/nasa-brand-center/images-and-media/): "NASA content ... generally
  are not subject to copyright in the United States." Aviso do EONET (https://eonet.gsfc.nasa.gov/what-is-eonet): "All EONET
  metadata and services are intended to be used for visualization and general information purposes only and should not be
  construed as 'official' with regards to spatial or temporal extent." -> o cliente mostra como informativo, com link para a
  fonte de cada evento (InciWeb/IRWIN, JTWC, ...), que guardamos em `url`.
  O endpoint geral `/api/v3/events` respondeu 500 em 2026-11-17; o ETL usa uma chamada por categoria (9 chamadas), que funciona.
- Categorias usadas: wildfires, severeStorms, volcanoes, floods, landslides, dustHaze, tempExtremes, drought, snow. Fora:
  earthquakes (o USGS já cobre), seaLakeIce (icebergs acompanhados há anos, não é "agora"), manmade, waterColor.
- Amostra de 2026-11-17: 104 terremotos M4.5+, 7 incêndios, 3 tempestades (114 eventos). Títulos em inglês, como na fonte.
- EONET: um ponto por evento, na geometria MAIS RECENTE (posição atual da tempestade); polígono -> média do anel externo.

## Contract delta (CR-015)
```
LiveEvent { id: string /* "usgs:<id>" | "eonet:<id>" */,
            type: "earthquake"|"wildfire"|"severe_storm"|"volcano"|"flood"|"landslide"|"dust_haze"|"temp_extreme"|"drought"|"snow",
            lat: number, lng: number, magnitude: number|null, magnitude_unit: string|null /* USGS magType ("mww"...) or EONET unit ("kts", "acres"...) */,
            title: string /* verbatim, English */, url: string|null /* event page at the source */,
            time: string /* ISO 8601 UTC; EONET: date of its latest position */, source: "usgs"|"eonet" }
GET /v1/live/events?since=&type= -> { items: LiveEvent[] /* newest first */, fetched_at: string|null, sources: Source[] }
    since: ISO 8601, default and floor = 7 days ago; type: comma-separated, unknown -> 422.
    Not under the data_version ETag: Cache-Control "public, max-age=300", no ETag.
```

## Design
- Migração **0022** (`live_events`, aditiva), depois de 0020 (032) e 0021 (033): **mergear 032, 033, 034 nessa ordem**.
- `python -m etl live-events` -> `data_out/live_events.json` `{fetched_at, ok: {usgs, eonet}, items}`.
- `python -m atlas_api.cli import-live-events`: troca as linhas das fontes com `ok: true` (fonte que falhou mantém as
  anteriores), apaga o que tem mais de 7 dias, grava `meta.live_fetched_at`. Não mexe no `data_version` (rodando a cada
  30 min, invalidaria os ETags de todas as rotas); `/v1/live/*` fica fora do cache por ETag (`cache.py`).
- Job: `.github/workflows/live-events.yml`, cron `7,37 * * * *` (a cada 30 min). Secret: `DATABASE_URL` (o mesmo do
  `news.yml`; nenhum segredo novo).

## Web (para o espelho em atlas-web)
- Camada "Acontecendo agora" no globo: um ponto pulsando por evento; cor por `type`; raio do terremoto pela `magnitude`.
  Atualizar a cada 5 min no máximo (o cache da rota é 5 min). Tooltip: `title`, tempo relativo ("há 3 h"), magnitude com
  unidade; clique abre `url`. Filtro por tipo (`?type=`).
- Créditos visíveis: "Terremotos: U.S. Geological Survey" e "Eventos naturais: NASA EONET (informativo, não oficial)".

## Tarefas
- [x] licenças lidas e citadas
- [x] ETL `live-events`, migração 0022, `import-live-events`, `GET /v1/live/events`, workflow, testes com respostas gravadas
- [x] CR-015, `openapi.generated.json`, `import-prod-034.ps1` ensaiado
- [ ] web (outra sessão)

## Decisões abertas
- Limite de magnitude (hoje M4.5+): baixar para M2.5+ só nas últimas 24 h dá ~mais 300 pontos/dia.
- Wikipedia "Current events" (B11) fica para outra spec.
