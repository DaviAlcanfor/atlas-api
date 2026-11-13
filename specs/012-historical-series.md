# 012 - Viagem no tempo: fronteiras, países antigos e séries históricas
Status: in progress (etapa 1 feita em 2026-11-13: retratos + /v1/snapshots; faltam entidades/links, fatos e séries) | Contrato: v2 | Web: atlas-web/specs/012-time-travel.md | Executor: Opus

## Por quê
Slider de ano que troca o mapa para as fronteiras da época e mostra cada entidade como era (nome, bandeira, governante, capital,
regime, população), com estilo de mapa da época (estilos: spec web 012).

## Fontes pesquisadas (2026-11-12)
| Fonte | Cobertura | Licença (conferida) | Uso |
|---|---|---|---|
| **Cliopatria** (Seshat Global History Databank; github.com/Seshat-Global-History-Databank/cliopatria, Zenodo 13363121; artigo Scientific Data 2025, doi 10.1038/s41597-025-04516-9) | 3400 a.C. a 2024, 1600+ entidades políticas, polígonos EPSG:4326, linhas com `FromYear`/`ToYear` (inteiros, negativo = a.C.), `Name`, `Type` (POLITY/RELATION), `Area` km², `Wikipedia`, `Wikidata` por linha; arquivo único `cliopatria.geojson.zip` (46 MB), release v0.2.1 de 2026-10-03 | **CC BY 4.0** (LICENSE.md: uso, adaptação e redistribuição com crédito, link da licença e indicação de mudanças) | **fonte principal das fronteiras** |
| historical-basemaps (aourednik) | 54 retratos fixos de −123000 a 2010 (ex.: 1815, 1878, 1880, 1900...), sem Wikidata | GPL-3.0 | não usar (retratos esparsos, sem ligação com Wikidata, licença copyleft nos dados) |
| CShapes 2.0 (ETH/PRIO) | Estados 1886-2019, preciso | CC BY-NC 4.0 (repositório ETH; outro catálogo diz BY-NC-SA) | **não usar em produção** (não comercial); só para checar 1886-2019 |
| OpenHistoricalMap | tiles vetoriais `vtiles.openhistoricalmap.org/{z}/{x}/{y}.pbf`, filtro por `start_decdate`/`end_decdate`, ótimo em escala local, cobertura global desigual | a confirmar (provável ODbL) | futuro: zoom em cidades/províncias antigas |
| Wikidata | bandeiras (P41 com P580/P582), capitais (P36 com datas), governantes (P35/P6, P1906/P1313 → P39), forma de governo (P122), sucessão (P1365/P1366, P155/P156) | CC0 | fatos de cada entidade antiga, via o `Wikidata` do Cliopatria |
| Maddison Project 2023 / V-Dem / OWID-HYDE | PIB pc, regime (`v2x_regime`), população histórica | CC BY 4.0 / CC BY-SA 4.0 / CC BY 4.0 | séries por ano (seção "Séries") |

Antes de codar: reler e citar os termos de cada uma nesta spec (regra do AGENTS.md), e registrar a versão/sha256 do arquivo do Cliopatria.

## Pipeline de fronteiras (`python -m etl cliopatria`, grupo etl)
1. Baixar o release fixado (v0.2.1), conferir sha256, ler com geopandas/shapely (dependência só do grupo `etl`).
2. Anos de retrato (~130): a cada 100 anos de −3400 a 1400; 50 até 1700; 25 até 1800; 10 até 1900; 5 até 1990; anual 1991-2024;
   mais anos-chave: 1492, 1648, 1789, 1815, 1871, 1914, 1918, 1939, 1945, 1989, 1991. Lista em `content/snapshot_years.yaml`.
3. Para cada ano: linhas `Type == POLITY` com `FromYear <= ano <= ToYear`; simplificação preservando topologia (TopoJSON quantizado,
   meta ≤ 600 KB por arquivo; medir e registrar); propriedades por feição: `name`, `wikidata`, `polity_id`.
   `RELATION` (vassalagens, uniões) fica para uma segunda etapa (desenhar como contorno tracejado).
4. Saída: `data_out/historical/world_<ano>.topo.json`; upload para Supabase Storage, bucket público `atlas-geometry` (mesmo esquema de
   credenciais da spec 019; pulado quando sem credenciais). Não versionar esses arquivos no git (~70 MB).
5. Banco: `polities` recebe as entidades do Cliopatria (id = slug do nome; `wikidata`; início/fim = união das faixas; nome pt-BR do
   Wikidata, senão o do Cliopatria); `snapshots` com `feature_count` e `link_coverage`; `snapshot_links` automáticos pelo Wikidata
   (`status: "auto"`), com sobrescritas em `content/polity_links.yaml` (`curated`). Os 8 placeholders históricos atuais são substituídos
   pelas entidades reais (ottoman-empire, soviet-union... continuam como ids, ligados ao Wikidata).
6. Continuidade com países modernos: P1366/P1365 e P155/P156 do Wikidata viram `predecessors`/`successors` (já existe no contrato).

## Fatos de cada entidade antiga (`etl wikidata-polities`)
Para cada `wikidata` do Cliopatria: bandeiras com datas (P41 + qualificadores; imagem do Commons com licença por arquivo, como na spec 006),
capitais com datas, forma de governo, governantes (reaproveitar `etl wikidata-leaders` com o item da entidade), descrição pt-BR e
extrato da Wikipedia (CC BY-SA) para o painel.

## Séries históricas (mantido da versão anterior)
Observações padronizadas por `polity_id` (população, PIB pc, tipo de regime, índice de democracia), crosswalk em `content/crosswalk.yaml`,
catálogo de métricas, regras: sem ano 0, `precision` em todo valor, uma fonte por valor, nunca interpolar.

## Contract delta (v2, aditivo onde possível)
```
SnapshotInfo.geometry_url: pode ser URL absoluta (Storage) além de caminho relativo; formato TopoJSON (objeto "polities")
Feição histórica: properties { name: string, wikidata: string|null, polity_id: string|null }   (substitui NAME/SUBJECTO/PARTOF/BORDERPRECISION)
GET /v1/snapshots/{year}/links -> { snapshot_year, links: [{ wikidata, polity_id, status }] }
PolityDetail += { wikidata: string|null, flag: { url, from_year, to_year, image: Image|null }|null, capital: { name, lat, lng }|null,
                  government: string|null }
GET /v1/polities/{id}/leaders?year= -> { items: Leader[] }         (mesmo tipo Leader da v1.1; `year` filtra quem governava)
GET /v1/metrics; GET /v1/polities/{id}/series/{metric}; GET /v1/map?metric=&year=   (séries, como antes)
```
Atribuição obrigatória no front: "Fronteiras: Cliopatria (Seshat Global History Databank), CC BY 4.0, simplificadas".

## Tarefas
- [x] reler termos e citar; fixar versão + sha256 (v0.2.1, sha256 no `etl/cliopatria/pipeline.py`; LICENSE.md lido em 2026-11-13)
- [x] `etl cliopatria`: 130 retratos, 35,8 MB no total, maior 492 KB (medido 2026-11-13); 1.123 de 1.420 entidades com nome pt-BR.
      Decisões da etapa 1 (CR-005): GeoJSON em vez de TopoJSON (já cabe no limite só com grade de 0,01 grau) e arquivos no repo
      web (`public/data/historical`) em vez do Storage (nunca configurado; menos uma peça). Agregados "(British Empire)" saem
      porque se sobrepõem aos componentes, que guardam `member_of`. `snapshots` importado por `import-facts`.
- [ ] polities/snapshots/links no banco; migração dos 8 placeholders
- [ ] `etl wikidata-polities` (bandeira, capital, governo, governantes com datas)
- [ ] endpoints v2 + testes; CR-004 com o texto exato do contrato v2
- [ ] séries (Maddison, V-Dem, OWID) depois do mapa funcionando
