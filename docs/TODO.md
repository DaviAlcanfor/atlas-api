# Atlas API: o que falta fazer

Estado em 2026-11-10. Fases definidas no prompt original (0 a 4). Atualize este arquivo ao avançar.

## Feito
- Fase 0: contrato copiado, scaffold, modelos Pydantic, rotas stub com fixtures JSON, `/v1/health`, `openapi.generated.json`.
- Organização: `config` (pydantic-settings), `deps` (injeção), `errors` (problem+json), lifespan, `routers/`, `schemas/`.
- ETL REST Countries escrito (cliente, modelos, transform, pipeline) com testes do transform.
- ORM (10 tabelas), Alembic, migrations 0001 (schema) e 0002 (busca) **escritas, ainda não aplicadas**, docker-compose.

## Bloqueios imediatos (precisam de você)
- [ ] Abrir o Docker Desktop e rodar `make db-up` + `make migrate` para testar as migrations no Postgres local.
- [ ] Autorizar aplicar as migrations no Supabase (banco `lxpgszopplawalyvwtot`, hoje vazio).
- [ ] Corrigir `RESTCOUNTRIES_API_KEY` no `.env` (deu 401; a doc mostra chaves `rc_...`) e rodar `make etl-restcountries`.
- [ ] Trocar a senha do banco Supabase (ela foi colada no chat).
- [ ] Reconfigurar o MCP do Supabase: hoje aponta para outro projeto (`qskdjqqyuejeyzpkszyf`).
- [ ] Decidir sobre os termos do REST Countries (ver Riscos).
- [ ] Criar o `.fastapicloudignore` (a criação foi bloqueada por permissão; sugestão de conteúdo em AGENTS.md/conversa: excluir `.git`, `.venv`, `.env*`, `etl/`, `etl_cache/`, `data_out/`, `content/`, `tests/`, `scripts/`, `docs/`, caches). Formato a confirmar na doc do FastAPI Cloud.

## Fase 1: banco, importador, endpoints reais
- [ ] Testar/ajustar migrations 0001 e 0002 em Postgres real.
- [ ] Testes contra Postgres real (docker-compose): fixture de sessão com banco de teste isolado.
- [ ] Helpers de regras de negócio + testes (incluindo BCE e bordas): `year_distance`, existe-no-ano (inclusivo), nome-no-ano, snapshot mais próximo (empate -> anterior), `has_content`.
- [ ] Importador `python -m atlas_api.cli import-content`: upsert idempotente em uma transação; valida referências, anos, períodos de nome sem sobreposição, sucessão acíclica, fontes dos eventos; recalcula `meta.data_version` (hash do conteúdo) e imprime resumo.
- [ ] `content/` (polities/*.yaml, sources.yaml, succession.yaml, snapshot_links.csv) e `seed_legacy/{AT,BR,DE,EG,JP}.json` convertidos (precisão "circa" para datas antigas).
- [ ] **PARAR e aguardar sua aprovação** nas decisões de modelagem: (1) Alemanha (Império -> Weimar -> Nazista -> RFA, RDA absorvida em 1990); (2) Iugoslávia (propor e listar simplificações); (3) períodos de nome (Constantinopla/Istambul). Marcar escolhas políticas.
- [ ] Seed dos ids do contrato (8 modernos + 8 históricos), só com fontes citáveis; incerto = `# TODO verify`.
- [ ] Trocar `FixtureStore` por consultas SQLAlchemy nos routers (countries, polities com `year`, detalhe, search, meta). Remover `fixtures/` quando acabar.
- [ ] Busca: sem acento, sem caixa, prefixo acima de substring, nomes atuais e históricos, dedupe por polity (usar `lower(f_unaccent(col))`, mesma expressão do índice).
- [ ] `/v1/health` com checagem real do banco (`db: "error"` quando cair); mapear `SQLAlchemyError` -> 503 (`ServiceUnavailableError` já existe).
- [ ] Engine no lifespan (criar e `dispose`), `get_session` como dependência.
- [ ] Teste de conformidade: todo exemplo do contrato valida contra os modelos Pydantic.

## Fase 2: REST Countries
- [ ] Rodar o ETL com a chave correta; conferir o formato real da lista paginada e se `response_fields` é aceito no endpoint de lista.
- [ ] `import-facts`: `data_out/facts.json` -> `country_facts` (+ fonte `restcountries` em `sources`).
- [ ] Mesclar fatos em `/countries` e `/countries/{iso2}` (campos do contrato; `population.year` nulo).
- [ ] Atribuição "REST Countries" com link no front (termos de uso).

## Fase 3: snapshots e geometria
- [ ] Antes de codar: reportar anos disponíveis em `historical-basemaps` (perto de 1500, 1700, 1815, 1880, 1914, 1920, 1945, 1960, 1994), tamanhos antes/depois da simplificação e implicações da licença GPL-3.0.
- [ ] `etl modern-geometry`: Natural Earth 50m, propriedade `ISO2`, tratar `-99` (França, Noruega...) via `*_EH` ou lista de correções, Kosovo = XK, relatar não casados e tamanho; listar países pequenos demais para o `marker`.
- [ ] `etl snapshots`: baixar anos, simplificar preservando topologia (mapshaper via npx ou método topológico; medir lacunas), < ~1,5 MB cada, gerar `world_<year>.geojson` e `snapshots.json`.
- [ ] `etl link-snapshots`: propor linhas para `content/snapshot_links.csv` (exato/alias; resto `unresolved`), nunca sobrescrever `curated`, imprimir cobertura por snapshot.
- [ ] Endpoints de snapshots reais (`link_coverage`, `nearest` com `distance_years`, `links`).
- [ ] `make sync-geometry` (usa `WEB_PUBLIC_DATA_DIR`; sem a variável, imprime instruções).
- [ ] `NOTICE.md` com atribuição e aviso GPL-3.0 do historical-basemaps.

## Fase 4: cache, desempenho, deploy
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
- REST Countries: plano Free = 1.000 req/mês, 20 req/10 s, uso não comercial; termos permitem cachear dados por no máximo 3 dias e proíbem re-expor os dados como API/dataset própria. Guardar em `country_facts` e servir pelos endpoints pode conflitar; consultar o suporte antes do deploy (não é decisão jurídica minha).
- Host direto do Supabase é só IPv6: usar sempre o pooler (modo session, porta 5432). Modo transaction (6543) costuma quebrar prepared statements do psycopg 3.
- FastAPI Cloud Hobby faz scale-to-zero: a primeira requisição após ociosidade pode ser lenta.
- Valores das fixtures são placeholders, não história curada.
