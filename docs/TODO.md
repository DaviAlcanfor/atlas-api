# Atlas API: o que falta fazer

Estado em 2026-11-10. Fases definidas no prompt original (0 a 4). Atualize este arquivo ao avançar.

## Feito
- Fase 0: contrato copiado, scaffold, modelos Pydantic, rotas stub com fixtures JSON, `/v1/health`, `openapi.generated.json`.
- Organização: `config` (pydantic-settings), `deps` (injeção), `errors` (problem+json), lifespan, `routers/`, `schemas/`.
- ETL REST Countries escrito (cliente, modelos, transform, pipeline) com testes do transform.
- ORM (10 tabelas), Alembic, migrations 0001 (schema) e 0002 (busca) **escritas, ainda não aplicadas**, docker-compose.

## Bloqueios imediatos (precisam de você)
- [ ] Abrir o Docker Desktop e rodar `make db-up` + `make migrate` para testar as migrations no Postgres local.
- [x] Migrations 0001/0002 já foram aplicadas no Supabase `<project-ref>` por engano (tabelas vazias); decidir se reverte (`alembic downgrade base`) ou mantém.
- [ ] Trocar a senha do banco Supabase (ela foi colada no chat).
- [ ] Reconfigurar o MCP do Supabase: hoje aponta para outro projeto (`qskdjqqyuejeyzpkszyf`).
- [x] Termos do REST Countries lidos: não guardar no banco (ver Riscos).
- [x] `.fastapicloudignore` criado (formato ainda a confirmar na doc do FastAPI Cloud).

## Fase 1: banco, importador, endpoints reais
- [x] Migrations 0001 e 0002 testadas em Postgres local (upgrade/downgrade/upgrade).
- [x] Testes contra Postgres real: banco `atlas_test` isolado (`tests/conftest.py`).
- [x] Helpers de regras (`src/atlas_api/rules.py`) + testes.
- [x] Importador `import-content` (`importer.py`, `cli.py`) com testes sintéticos; falta o conteúdo real. Eventos sem fonte contam como não verificados no resumo.
- [ ] Migration 0003 `country_indicators` (depende do contrato v1.1, que ainda não está no repo).
- [ ] `content/markers.yaml` (iso2 -> lat, lng) com VA FM MH TO SG SC SM VC LC KN PW NR MC MT MV LI GD DM BB BH AG AD; coordenadas da Wikidata, revisadas por você.
- [ ] `content/` (polities/*.yaml, sources.yaml, succession.yaml, snapshot_links.csv) e `seed_legacy/{AT,BR,DE,EG,JP}.json` convertidos (precisão "circa" para datas antigas).
- [ ] **PARAR e aguardar sua aprovação** nas decisões de modelagem: (1) Alemanha (Império -> Weimar -> Nazista -> RFA, RDA absorvida em 1990); (2) Iugoslávia (propor e listar simplificações); (3) períodos de nome (Constantinopla/Istambul). Marcar escolhas políticas.
- [ ] Seed dos ids do contrato (8 modernos + 8 históricos), só com fontes citáveis; incerto = `# TODO verify`.
- [ ] Trocar `FixtureStore` por consultas SQLAlchemy nos routers (countries, polities com `year`, detalhe, search, meta). Remover `fixtures/` quando acabar.
- [ ] Busca: sem acento, sem caixa, prefixo acima de substring, nomes atuais e históricos, dedupe por polity (usar `lower(f_unaccent(col))`, mesma expressão do índice).
- [ ] `/v1/health` com checagem real do banco (`db: "error"` quando cair); mapear `SQLAlchemyError` -> 503 (`ServiceUnavailableError` já existe).
- [ ] Engine no lifespan (criar e `dispose`), `get_session` como dependência.
- [ ] Teste de conformidade: todo exemplo do contrato valida contra os modelos Pydantic.

## Fase 2: Wikidata e World Bank (substitui REST Countries)
- [x] Docs da Wikidata lidas (2026-11-11). Limites 60 s/consulta, 5 paralelas/IP e 429 só confirmados em resumo, não literalmente.
- [x] `etl wikidata` (`make etl-wikidata`) -> `data_out/wikidata.json`: 196 estados soberanos; cache bruto em `etl_cache/wikidata/` com `retrieved_at`. Bandeira: só o nome do arquivo (P41); falta ler a política do Commons para montar `flag_url`.
- [x] Decididos: Kosovo/Taiwan/Palestina incluídos; `flag_url` via flagcdn.com (196/196 verificados); `official_name` em pt-BR via `content/official_names_pt.yaml` (tradução NÃO verificada, revisar); `memberships` só ONU.
- [ ] Idiomas: Uruguai fica sem idioma oficial (a Wikidata não tem; vazio, não inventado). População com anos de 2005 a 2026.
- [x] Docs do World Bank lidas; `etl worldbank` (`make etl-worldbank`) -> `data_out/worldbank.json` (581 linhas: população, PIB per capita, expectativa de vida; último ano disponível). Faltam: TW e VA (todos), KP (PIB). A API mistura 79 agregados, filtrados pelos 196 iso2. Atribuição CC BY 4.0 obrigatória.
- [x] `content/markers.yaml` com 22 micro-estados (coordenada da capital na Wikidata); aguarda sua revisão.
- [ ] `import-indicators` e migration 0003: dependem do contrato v1.1 e do seed dos países.
- [ ] `import-facts` -> `country_facts`; `import-indicators` -> `country_indicators`; `sources` com `license` citada da fonte lida.
- [ ] Mesclar em `/countries*` (`population` da Wikidata com ano; ausente = null; `indicators` = ano mais recente por indicador).
- [x] Seed dos 196 países: opção A (placeholder 1946 / `century`), ver README. `import-content` e `import-facts` rodam no Postgres local (196 polities, 196 country_facts, 23 eventos legados não verificados).
- [x] `FixtureStore` removido: todos os endpoints leem do Postgres (`queries.py`); busca sem acento com prefixo antes de substring; `/health` verifica o banco; erro de banco vira 503; `connect_timeout` de 5 s. Snapshots vazios até a Fase 3 (nearest/links dão 404).
- [ ] DEPLOY NÃO FEITO: a produção ainda roda a versão com fixtures. O Supabase está vazio (migrations desfeitas em 2026-11-11); para publicar a versão nova é preciso: `alembic upgrade head`, `import-content` e `import-facts` no Supabase, `DATABASE_URL` (pooler) no FastAPI Cloud e só então `fastapi deploy`.
- [ ] Os 8 ids históricos do contrato existem como placeholders não verificados (`content/polities/*.yaml`, anos das fixtures da Fase 0), sem eventos nem sucessão.
- [ ] Notícias: GDELT bloqueou minhas chamadas ("one every 5 seconds"); não verificado. Ver conversa para as alternativas.

## Fase 3: snapshots e geometria
- [ ] Antes de codar: reportar anos disponíveis em `historical-basemaps` (perto de 1500, 1700, 1815, 1880, 1914, 1920, 1945, 1960, 1994), tamanhos antes/depois da simplificação e implicações da licença GPL-3.0.
- Geometria MODERNA é do repositório web (não fazer `etl modern-geometry`). Aqui só os snapshots históricos.
- [ ] `etl snapshots`: baixar anos, simplificar preservando topologia (mapshaper via npx ou método topológico; medir lacunas), < ~1,5 MB cada, gerar `world_<year>.geojson` e `snapshots.json`.
- [ ] `etl link-snapshots`: propor linhas para `content/snapshot_links.csv` (exato/alias; resto `unresolved`), nunca sobrescrever `curated`, imprimir cobertura por snapshot.
- [ ] Endpoints de snapshots reais (`link_coverage`, `nearest` com `distance_years`, `links`).
- [ ] `make sync-geometry` (usa `WEB_PUBLIC_DATA_DIR`; sem a variável, imprime instruções).
- [ ] `NOTICE.md` com atribuição e aviso GPL-3.0 do historical-basemaps.

## Fase 4: cache, desempenho, deploy
- [x] Deploy conecta: `fastapi[standard]`, entrypoint em `[tool.fastapi]` e Python fixado em 3.13 (`requires-python` e `.python-version`), pois o servidor usou 3.15 e o psycopg pode não ter wheels.
- [ ] No painel do FastAPI Cloud, definir `DATABASE_URL` (pooler Supabase), `CORS_ORIGINS` e `LOG_LEVEL` como variáveis/segredos. Hoje a API não usa o banco, então sobe sem `DATABASE_URL`.
- [ ] ETag fraco = hash(data_version, path, query), 304 com `If-None-Match`, `X-Data-Version`, `Cache-Control: public, max-age=300, stale-while-revalidate=86400` (exceto `/health`).
- [ ] Cache em memória para `meta` e polities-por-ano, chave (data_version, year), invalidando quando `data_version` muda.
- [ ] Medir tempo de import e cold start local.
- [ ] Ler a doc do FastAPI Cloud: env vars/segredos, região, planos; confirmar formato do `.fastapicloudignore`; escolher versão do Python.
- [ ] Deploy (`fastapi deploy`) + Supabase (pooler modo session, mesma região da API) e runbook curto.
- [ ] Logging estruturado.
- [ ] Escape hatch (não construir a menos que precise): exportar endpoints de leitura como JSON estático.

## Qualidade e documentação
- [ ] README: modelo de dados, regras do "ano Y", como adicionar polity/sucessão/link de snapshot, rodar ETL e importação, deploy, limitações (fronteiras aproximadas, snapshots descontínuos, Kosovo/Taiwan/Crimeia e a escolha feita).
- [ ] Instalar `make` no Windows (ou manter as linhas `uv run` do Makefile) e checar CI.
- [ ] Cobertura de testes pedida: ETag/304, problem+json, busca sem acento, idempotência do importador, ciclo de sucessão.

## Riscos conhecidos
- REST Countries (termos lidos em 2026-11-11): Seção 5 proíbe reter dados "in primary, backup, derivative, or any other form" além de 3 dias; Seção 6 proíbe agregar o dataset em produto downstream. Por isso NÃO vai para o banco; `etl/restcountries/` fica só como referência.
- Host direto do Supabase é só IPv6: usar sempre o pooler (modo session, porta 5432). Modo transaction (6543) costuma quebrar prepared statements do psycopg 3.
- FastAPI Cloud Hobby faz scale-to-zero: a primeira requisição após ociosidade pode ser lenta.
- Valores das fixtures são placeholders, não história curada.
