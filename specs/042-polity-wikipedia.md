# 042 - Wikipedia dentro da viagem no tempo (resumo das entidades históricas)
Status: approved (o dono pediu em 2026-11-18: "na viagem no tempo, mostrar dentro do site as informações da Wikipedia da entidade") | Contrato: CR-018 | Web: geo/specs/012-time-travel.md

## Por quê
Hoje o painel histórico só mostra o link da Wikipédia. O front só fala com a API: ela guarda o resumo (lead do artigo) de cada entidade.

## Dados (lido em 2026-11-18)
- Título do artigo: sitelink pt do Q-id (Wikidata, CC0, já em cache pelo `etl cliopatria`), senão o título em inglês que o Cliopatria traz.
- Texto: `GET https://{lang}.wikipedia.org/api/rest_v1/page/summary/{título}` -> `extract` (texto puro; `extract_html` nunca é guardado),
  `content_urls.desktop.page`, `revision`, `thumbnail.source`.
- Licença do texto, Termos de Uso da Wikimedia §7: o texto é CC BY-SA 4.0; o reúso exige crédito "Through hyperlink (where possible)
  or URL to the page or pages that you are reusing" (ou lista de autores) e "a licensing notice stating which license the work is
  released under ... along with either a hyperlink or URL to the text of the license". A API devolve `attribution` pronta, `url` e `license_url`.
- Imagens: "Non-text media on the Projects are available under a variety of different licenses" (cada arquivo tem a sua). A miniatura
  fica gravada (`thumbnail_url`) mas NÃO é servida: a REST API não diz a licença do arquivo. Servir só depois de checar a licença no Commons.
- Limites (mediawiki.org/wiki/Wikimedia_APIs/Rate_limits): bot sem login com User-Agent conforme = 200 req/min; sem identificação = 10/min.
  Política de User-Agent: "<cliente>/<versão> (<contato>)", agentes genéricos (python-requests, curl) podem ser bloqueados (403).
  Decisão do dono: sem contato pessoal nas requisições; o agente é só `atlas-etl/1.0`. Se a Wikimedia bloquear, acrescentar contato.
  Ritmo: ~6 req/s com pausa de 0,15 s, retry/backoff do `_get_json`, cache em `etl_cache/wikipedia/polities/`.
- Cobertura: ver "Resultado da amostra".

## Contract delta
CR-018 (`contract/CHANGE_REQUESTS.md`): `WikipediaSummary`, `PolityDetail.wikipedia_summary`, `GET /v1/entities/{wikidata_qid}/wikipedia`.
(`PolityDetail.summary` já existe, é o texto curado: por isso o campo novo se chama `wikipedia_summary`.)

## Design
- Tabela `polity_summaries` (migração 0025, aditiva), chave = Q-id: a maioria das entidades do Mapa (Cliopatria) não é linha de `polities`.
- `etl wikipedia-polities [Q-ids]` -> `data_out/polity_summaries.json`; `python -m atlas_api.cli import-polity-summaries` reconstrói só essa tabela.
- Sem artigo/sem texto (desambiguação, 404): sem linha, a API devolve 404 (endpoint) ou null (campo).
- Testes sem rede: resposta REST gravada em `tests/fixtures/wikipedia_summary_otomano_pt.json`.

## Tarefas
- [x] termos lidos e citados
- [x] migração 0025, modelo, ETL, import, endpoint, campo, testes
- [x] CR-018, openapi.generated.json
- [ ] dono cola CR-018 no CONTRACT.md (os dois repos); rodar o ETL completo e o import em produção; web mostra o resumo e a atribuição

## Resultado da amostra
Ver o corpo do PR.
