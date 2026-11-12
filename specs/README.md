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
| 003 | [Pistas de GeoGuessr (Wikidata)](003-geo-clues.md) | v1.1 | done (aguardando deploy (contrato v1.1 aplicado)) |
| 004 | [Regime de todos os países + glossário](004-glossary.md) | v1.1 | done (aguardando deploy (contrato v1.1 aplicado)) |
| 005 | [Coordenadas da capital](005-capital-coords.md) | v1.1 | done (aguardando deploy (contrato v1.1 aplicado)) |
| 006 | [Governantes e espectro político](006-leaders-spectrum.md) | v1.1 / v1.2 | in progress (v1.1 feito) |
| 007 | [Pessoas importantes](007-notable-people.md) | v1.1 | done (aguardando deploy (contrato v1.1 aplicado)) |
| 008 | [Notícias geopolíticas (GDELT + Jev)](008-news.md) | v1.2 | approved |
| 009 | [Moeda, câmbio e economia](009-currency.md) | v1.2 | done local (CR-003 pendente) |
| 010 | [Música](010-music.md) | v1.2 | approved |
| 011 | [Vídeos de história](011-history-videos.md) | v1.2 | approved |
| 012 | [Séries históricas padronizadas](012-historical-series.md) | v2 | approved |
| 015 | [Perfil: como vive o povo](015-country-profile.md) | v1.2 | done local (CR-003 pendente) |
| 016 | [História expandida por períodos](016-history-expanded.md) | v1.2 | approved |
| 017 | [Idiomas oficiais e outros](017-languages.md) | v1.2 | approved |
| 018 | [Ideologias e pensadores](018-ideologies.md) | v1.2 | approved |
| 019 | [Correções de dados (data_version, DK, imagens, capitais, carga)](019-data-fixes.md) | - | done local (bucket de imagens: falta credencial) |

001, 002, 013 e 014 são só do web. Plano de execução, checklist e avaliação de stack: `atlas-web/specs/PLAN.md` e `atlas-web/specs/ADR-001-stack.md`.

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
