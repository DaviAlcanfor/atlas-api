# 008 — Notícias
Status: draft | Contrato: v1.2 | Web: atlas-web/specs/008-news.md | Substitui: CR-001

## Dados
| | GDELT DOC 2.0 API (por país) | Wikipedia "Portal:Current events" (mundo) |
|---|---|---|
| O que dá | artigos (título, url, domínio, idioma, data) de veículos do mundo todo, ~65 idiomas | resumo diário curado, com links pros veículos |
| Português | sim (`sourcelang:portuguese`) | não |
| Chave | não | não (MediaWiki Action API, `action=parse&prop=wikitext`) |
| Licença | uso livre com citação ao GDELT Project (**ler e citar antes de codar**) | CC BY-SA 4.0: atribuir e linkar |
| Limite | 1 req / 5 s; a rede do trabalho recebe 429 em tudo | folgado |

Busca: `query="<nome em inglês>" sourcelang:portuguese`, depois sem filtro de idioma,
`mode=ArtList&format=json&maxrecords=50&timespan=7d&sort=DateDesc`.
**Spike obrigatório** (fora da rede do trabalho, ex.: no próprio GitHub Actions): confirmar que busca em inglês acha artigos em
português e avaliar relevância em BR, JP, DE, EG, AT. Se ruim, testar `theme:`; `sourcecountry:` filtra o país do *veículo*, não o assunto.

## Contract delta
```
NewsItem { id, title, url, outlet, language /* ISO 639-1 */, published_at, countries: string[], origin: "gdelt"|"wikipedia" }
GET /v1/countries/{iso2}/news?limit=  -> { items: NewsItem[], fetched_at: string|null }    limit default 20, max 50
GET /v1/news?date=&limit=             -> { items: [{ date, text, links: [{ title, url }] }], source: Source, fetched_at: string|null }
Cache-Control nessas rotas: max-age=900. `title` no idioma original (exceção ao "pt-BR only").
```

## Design
**Job agendado, não busca ao vivo**: 196 países × 5 s = ~17 min, impossível dentro de uma requisição; cache em memória some
quando o FastAPI Cloud reinicia.
- Tabelas: `news_items` (url única, título, outlet, idioma, published_at, origin, fetched_at), `news_item_countries` (n:n),
  `world_news_days` (date pk, itens jsonb, fetched_at).
- `python -m atlas_api.cli import-news`: países com pausa de 5 s; normaliza URL (sem `utm_*`, sem `#`); dedup por URL e por título
  normalizado; apaga > 30 dias; **uma transação por país** (falha num país preserva o lote anterior dele).
- Wikitext do dia → texto + links na API (o web nunca recebe HTML).
- GitHub Actions: `.github/workflows/news.yml`, `cron: "0 */6 * * *"`, secret `DATABASE_URL` (Supabase).
- AGENTS.md: regra "só `import-content` escreve" vira "só comandos do CLI escrevem; `import-news` só nas tabelas de notícias".

## Tarefas
- [ ] spike GDELT (workflow manual `workflow_dispatch` que só imprime resultados); registrar aqui
- [ ] ler e citar termos GDELT e Wikipedia
- [ ] migração, `import-news`, testes com respostas gravadas
- [ ] endpoints + cache; workflow agendado; atualizar AGENTS.md

## Decisões abertas
1. Job agendado (recomendado) ou busca ao vivo?
2. Português primeiro + outros idiomas completando (recomendado) ou só português?
3. Retenção 30 dias (recomendado)? Frequência 6 h (recomendado) ou diária?
