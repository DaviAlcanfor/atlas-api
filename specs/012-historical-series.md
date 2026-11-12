# 012 — Séries históricas padronizadas e snapshots
Status: draft | Contrato: v2 (aditivo) | Web: atlas-web/specs/012-time-travel.md | Relaciona: `indicators` (CR-1 do web)

## Por quê
O web terá um slider de ano que troca fronteiras e dados. A API precisa (1) ter snapshots de fronteira e (2) servir dados de
épocas diferentes num formato único.

## Estado atual
- `GET /v1/meta` → `snapshot_years: []`: nenhum snapshot importado. Primeiro bloqueio (`sync-geometry`, listado no AGENTS.md).
- As 8 polities históricas são placeholders não verificados.

## Dados
Ideia central: toda série vira uma **observação** ligada a uma *polity* (não a um país moderno), para que Império Otomano,
URSS e Brasil Império usem o mesmo esquema.
| Métrica | Fonte | Período | Licença (a confirmar) |
|---|---|---|---|
| População | World Bank (1960+; ETL existe); Our World in Data / HYDE (antes) | −10000 a hoje | CC BY 4.0 |
| PIB per capita | Maddison Project Database 2023 | ano 1 a hoje, esparso | CC BY 4.0 |
| Tipo de regime | V-Dem `v2x_regime` (4 categorias) | 1789+ | CC BY-SA 4.0 |
| Índice de democracia | V-Dem `v2x_polyarchy` (0–1) | 1789+ | CC BY-SA 4.0 |
| Fronteiras | historical-basemaps (planejado); CShapes 2.0 como alternativa (1886–2019) | — | GPL-3.0 / a confirmar |

Padronização:
1. **Crosswalk** `content/crosswalk.yaml`: id na fonte (COW do V-Dem, código Maddison, ISO3 do World Bank) → `polity_id` + intervalo de anos.
   É o trabalho manual mais importante (ex.: V-Dem "Germany" 1949–1990 = Alemanha Ocidental).
2. **Catálogo de métricas** em `content/metrics.yaml`: id, rótulo pt-BR, unidade, descrição, ordem de preferência de fontes.
3. **Regras** (com teste cada): sem ano 0; `precision` em todo valor; uma fonte por valor; conflito resolvido pela ordem do catálogo;
   nunca interpolar.

## Contract delta
```
Metric      { id, label, unit: string|null, description, kind: "number"|"category", categories: string[]|null, sources: Source[] }
Observation { year: int, value: number|string, precision: Precision, source_id: string }
GET /v1/metrics                                  -> { items: Metric[] }
GET /v1/polities/{id}/series/{metric}?from=&to=  -> { polity_id, metric, items: Observation[] }
GET /v1/map?metric=&year=                        -> { year, metric, items: [{ polity_id, value, source_id }] }
CountryDetail/PolityDetail += indicators: [{ metric, value, year, source_id }]   (último valor)
```

## Design
- Tabelas `metrics`, `observations` (polity_id, metric_id, year, value_num, value_cat, precision, source_id; PK polity+metric+year+source).
- ETLs em ordem: World Bank (adaptar o existente) → V-Dem → Maddison → OWID. Arquivos baixados, não scraping.
- `/v1/map` com índice (metric_id, year).

## Tarefas
- [ ] decidir fronteiras; importar snapshots + vínculos (desbloqueia o slider do web)
- [ ] tabelas + catálogo + crosswalk (8 seeds históricos + 196 modernos)
- [ ] ETLs na ordem acima, cada um citando licença; testes de padronização

## Decisões abertas
1. historical-basemaps (GPL-3.0) ou CShapes 2.0?
2. Começar só com população + regime V-Dem (recomendado)?
