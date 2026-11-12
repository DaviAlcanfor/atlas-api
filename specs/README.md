# Specs (API)

Uma spec por feature, numerada igual à spec do web (`atlas-web/specs/NNN-*.md`).
Status: `draft` → `approved` (só o dono do projeto aprova) → `in progress` → `done`. Sem código de feature em `draft`.

Regras:
- `contract/CONTRACT.md` continua FROZEN para agentes. Cada spec lista o "Contract delta" (só mudanças aditivas).
  Specs aprovadas da mesma fase viram uma CR única (ex.: "v1.1 = 003 + 004 + 005 + 006a + 007"); o dono atualiza o contrato
  nos dois repos e só então endpoint/campo novo vai pra produção.
- Fonte nova: ler doc e licença ANTES de codar e citar na spec (regra do AGENTS.md).
- Testes sem rede: respostas de upstream gravadas em `tests/fixtures/`.

| # | Feature | Fase | Status |
|---|---|---|---|
| 003 | [Pistas de GeoGuessr (Wikidata)](003-geo-clues.md) | v1.1 | done (aguardando contrato v1.1) |
| 004 | [Regime de todos os países + glossário](004-glossary.md) | v1.1 | done (aguardando contrato v1.1) |
| 005 | [Coordenadas da capital](005-capital-coords.md) | v1.1 | done (aguardando contrato v1.1) |
| 006 | [Governantes e espectro político](006-leaders-spectrum.md) | v1.1 / v1.2 | in progress (v1.1 feito) |
| 007 | [Pessoas importantes](007-notable-people.md) | v1.1 | done (aguardando contrato v1.1) |
| 008 | [Notícias](008-news.md) | v1.2 | draft |
| 009 | [Moeda: cotações e PPP](009-currency.md) | v1.2 | draft |
| 010 | [Música](010-music.md) | v1.2 | draft |
| 011 | [Vídeos de história](011-history-videos.md) | v1.2 | draft |
| 012 | [Séries históricas padronizadas](012-historical-series.md) | v2 | draft |

001 e 002 são só do web (sem mudança na API).

## Template
```md
# NNN — Título
Status: draft | Contrato: vX.Y | Web: atlas-web/specs/NNN-*.md

## Por quê
## Dados (fonte, licença citada, cobertura, o que fica null)
## Contract delta
## Design (migração, ETL, import, endpoint, cache)
## Tarefas
## Decisões abertas
```
