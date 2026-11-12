# 005 — Coordenadas da capital
Status: done (aguardando deploy (contrato v1.1 aplicado)) | Contrato: v1.1 | Web: atlas-web/specs/005-capital-subdivisions.md

## Por quê
O web quer marcar a capital no globo. Estados/províncias são geometria e ficam no web (regra do AGENTS.md).

## Dados
**Já existe**: a pipeline do Wikidata busca P36 + P625 e o banco tem `countries.capital_lat/capital_lng`. Só não está no contrato.
Falta: países com mais de uma capital (ZA, BO, ...) hoje ficam com uma só (a de rank preferido).

## Contract delta
`CountrySummary += capital_coords: [{ name: string, lat: number, lng: number }]` (`[]` = sem dado).
Lista em vez de objeto para comportar várias capitais.

## Design
- Fase 1: lista de 1 item a partir das colunas atuais (sem migração).
- Fase 2 (opcional): tabela `capitals` para várias capitais.

## Tarefas
- [x] schema + query + teste (fase 1): 196/196 países com 1 coordenada (2026-11-11)
- [ ] fase 2 (várias capitais): não feita
