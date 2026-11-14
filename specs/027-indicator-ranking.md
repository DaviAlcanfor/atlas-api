# 027 - Ranking de países no mapa ("tier list")
Status: done (API) | Contrato: v1.4 (CR-006) | Web: atlas-web/specs/027-indicator-ranking.md

## Pedido (2026-11-13)
"No próprio mapa ter um seletor de indicador, tipo top 10 países IDH, top 10 densidade populacional, e aí faz o heatmap."

## Data
Os 24 indicadores já importados (Banco Mundial CC BY 4.0, PNUD CC BY 3.0 IGO) com `indicator_latest.rank` calculado no
`import-facts`; densidade = população ÷ área (Wikidata, CC0), igual ao painel. Fica de fora o fator de conversão PPC (sem ordem).
Correção junto: área do Wikidata com vários valores (Bósnia aparecia com 10 km², a área de água): `pick_area`.

## Tarefas
- [x] `GET /v1/indicators` e `GET /v1/indicators/{id}/ranking` + testes
- [x] `pick_area` + teste; `wikidata.json` refeito
- [x] CR-006 aplicado ao contrato dos dois repos
