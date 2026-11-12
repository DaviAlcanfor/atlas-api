# 008 - Notícias geopolíticas (GDELT + Jev)
Status: approved | Contrato: v1.2 | Web: atlas-web/specs/008-news.md | Substitui: CR-001 | Executor: Opus

## Decisões (aprovadas pelo dono em 2026-11-12)
- Job agendado (não busca ao vivo). Português primeiro, outros idiomas completando. Retenção 30 dias. Frequência: a cada 6 h.
- A seleção "é geopolítico?" é feita pelo **Jev** (TypeSafe System One), não por lista de palavras.
- Sem resumo por IA: o Atlas guarda e mostra só título, URL, veículo, data, idioma e as classificações.

## Dados
- **Candidatos**: GDELT DOC 2.0 API, `mode=ArtList&format=json&maxrecords=250&timespan=6h&sort=DateDesc`, consultas por tema
  (`theme:` de conflito, diplomacia, eleições, sanções, protestos; lista em `content/news_queries.yaml`) e `sourcelang:` por/eng/spa.
  Limite do GDELT: 1 requisição / 5 s; a rede do trabalho recebe 429, então o job roda no GitHub Actions.
  **Ler e citar os termos do GDELT nesta spec antes de codar.**
- **Classificação**: TypeSafe, SDK `typesafe-sdk` (`pip install typesafe-sdk`, grupo `etl`, nunca no processo da API),
  modelo `jev-latest` (alias de jev-1.14.0), chave em env `TYPESAFE_API_KEY` (secret do GitHub Actions; console.typesafe.ai).
  Preço lido em 2026-11-12: US$ 0,042 por milhão de tokens de entrada (saída grátis). Limites: 64k tokens por requisição, 32k por pergunta.
  Rate limit por organização (ver console).
  Docs lidas: docs.typesafe.ai/sdk/python.md, /primitives/noul.md, /primitives/choice.md, /api.md, /models.md.
  **Verificar no SDK instalado** se as respostas se leem em `response.answers[id]` ou `response.nouls[id]` (a doc tem os dois).

## Desenho das perguntas (uma requisição por manchete, todas as perguntas juntas)
State: `{ "headline": título, "outlet": domínio, "language": iso639, "countries_mentioned": [nomes detectados em código] }`.
- `geo` (Noul): "Esta manchete trata de relações entre Estados, conflito armado, segurança internacional, diplomacia, sanções,
  eleições ou mudanças de governo com impacto além de um assunto local? Esportes, celebridades, crimes comuns e economia doméstica não contam."
- `type` (Choice): conflict | diplomacy | election | sanctions | agreement | protest | coup | economy_policy | other,
  cada opção com uma frase de definição em `criteria`.
- `about_<ISO2>` (Noul, uma por país candidato, máx. 5): "A manchete é sobre `<país>` (ator ou lugar do evento), não só uma menção?"
  Países candidatos vêm de código (casamento de nomes/gentílicos pt/en/es com uma tabela do Wikidata), o Jev só confirma.
Política em código (sem nova inferência para mudar): `geo >= 0.7` entra no feed; `0.5 <= geo < 0.7` entra como "talvez relevante";
`< 0.5` descarta. País entra em `countries` se `about >= 0.6`. Limiares avaliados num conjunto rotulado de 200 manchetes
(`tests/fixtures/news_labeled.jsonl`, rotulado à mão) antes de ligar o job; registrar precisão/recall aqui.
Custo estimado: ~2.000 manchetes/dia × ~400 tokens ≈ 0,8 M tokens/dia ≈ US$ 0,03/dia.

## Contract delta (v1.2)
```
NewsItem { id, title, url, outlet, language, published_at, countries: string[],
           event_type: "conflict"|"diplomacy"|"election"|"sanctions"|"agreement"|"protest"|"coup"|"economy_policy"|"other",
           geopolitical_p: number, origin: "gdelt" }
GET /v1/news?region=&type=&lang=&country=&min_p=&limit=&before= -> { items: NewsItem[], fetched_at: string|null, next: string|null }
     min_p default 0.7; limit default 30, max 100; `before` = cursor (published_at,id)
GET /v1/countries/{iso2}/news?limit= -> { items: NewsItem[], fetched_at: string|null }
Cache-Control nessas rotas: max-age=900. `title` no idioma original (exceção ao "pt-BR only").
```

## Design
- Tabelas: `news_items` (url única normalizada, título, outlet, idioma, published_at, event_type, geopolitical_p, fetched_at),
  `news_item_countries` (n:n com `about_p`). Índices: (published_at desc), (event_type), (country).
- `python -m etl news` (grupo etl): busca GDELT → normaliza/deduplica (URL sem `utm_*`/`#`, título normalizado) → classifica no Jev
  (só itens novos; cache por URL) → escreve `data_out/news.jsonl`. `python -m atlas_api.cli import-news` grava (uma transação),
  apaga > 30 dias. Falha no Jev = item fica de fora desta rodada (nunca entra sem classificação).
- `.github/workflows/news.yml`: cron `0 */6 * * *` + `workflow_dispatch`; secrets `DATABASE_URL`, `TYPESAFE_API_KEY`.
- AGENTS.md: "só comandos do CLI escrevem no banco; `import-news` só nas tabelas de notícias".

## Tarefas
- [ ] ler termos do GDELT; spike (workflow_dispatch que só imprime 50 candidatos + respostas do Jev); rotular 200 manchetes; medir limiares
- [ ] migração; `etl news`; `import-news`; testes com respostas GDELT/TypeSafe gravadas (sem rede)
- [ ] endpoints + cache; workflow agendado; atualizar AGENTS.md
