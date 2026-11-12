# Atlas API

API somente leitura que serve **países modernos**, **entidades políticas históricas** (impérios, reinos, estados extintos), suas **linhas do tempo** e o **mapeamento entre polígonos de mapas históricos e essas entidades**.

> **Status:** em construção. As rotas leem dados reais do Postgres (197 países da Wikidata + 8 entidades históricas placeholders); v1.2 parte A (idiomas, perfil, economia, câmbio) existe só localmente; snapshots e notícias ainda não existem. O que falta está em [docs/TODO.md](docs/TODO.md).

## Por que existe

A mesma terra muda de "dono" político ao longo do tempo (Império Otomano → República da Turquia; Iugoslávia → vários estados). O dataset de mapas históricos ([historical-basemaps](https://github.com/aourednik/historical-basemaps)) só tem nomes por ano, sem códigos ISO. Esta API guarda:

1. entidades políticas com tempo de vida e períodos de nome;
2. ligações de sucessão entre elas;
3. um mapeamento curado (ano do snapshot, nome do polígono) → entidade;
4. linhas do tempo com precisão de data.

O valioso é o **modelo de dados e a curadoria**, não a camada HTTP.

## Stack

Python 3.12+ · [uv](https://docs.astral.sh/uv/) · FastAPI · Pydantic v2 · SQLAlchemy 2 (síncrono, psycopg 3) · Alembic · PostgreSQL (Docker local, Supabase em produção) · pytest · ruff · mypy (strict).

SQLAlchemy síncrono basta aqui: a carga é de leitura, com consultas curtas, e o FastAPI roda endpoints síncronos em um pool de threads.

## Estrutura

```
contract/            CONTRACT.md (CONGELADO: nunca editar) e CHANGE_REQUESTS.md
docs/                CONTRACT_NOTES.md (contrato → código) e TODO.md (o que falta)
src/atlas_api/
  main.py            fábrica do app + lifespan
  config.py          configurações (pydantic-settings)
  deps.py            injeção de dependências (Depends)
  errors.py          exceções de domínio → application/problem+json
  schemas/           modelos Pydantic = contrato campo a campo
  routers/           um arquivo por recurso (/v1/...)
  db/                modelos ORM e sessão
  fixtures/          dados de exemplo em JSON (provisório, some na Fase 1)
etl/                 CLI separada de ETL (não é importada pela API)
migrations/          migrations do Alembic
scripts/             utilitários (ex.: exportar o OpenAPI)
tests/
```

Regra de ouro: o processo da API **nunca importa** o grupo de dependências `etl` (pandas, geopandas...). Assim a imagem de deploy fica pequena e o cold start rápido.

## Começando

Pré-requisitos: Python 3.12+, `uv`, Docker Desktop.

```bash
uv sync                       # instala dependências (inclui dev)
cp .env.example .env          # preencha os valores (veja abaixo)
docker compose up -d --wait   # Postgres local        (make db-up)
uv run alembic upgrade head   # cria as tabelas        (make migrate)
uv run uvicorn atlas_api.main:app --reload --app-dir src   # (make dev)
```

Docs interativas em <http://localhost:8000/docs>.

> No Windows sem `make`, use as linhas `uv run ...` de cada alvo do [Makefile](Makefile).

### Variáveis de ambiente

Segredos **só** por variável de ambiente (ou `.env`, que o git ignora). Nunca commite um `.env` real.

| Variável | Para quê | Observação |
|---|---|---|
| `DATABASE_URL` | Conexão com o Postgres | `postgresql+psycopg://usuário:senha@host:porta/banco`. Caracteres especiais na senha devem ser codificados (`@` → `%40`). |
| `CORS_ORIGINS` | Origens permitidas | Separadas por vírgula. Ex.: `http://localhost:5173,https://seu-front.example` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT` | Pool de conexões por processo (padrão 5 / 2 / 3 s) | Sem conexão livre em `DB_POOL_TIMEOUT` s a API responde 503 em vez de travar. Total = processos × (size + overflow): manter abaixo do pool do Supabase (spec 019 item 5). |
| `DATA_VERSION_TTL` | Cache do `data_version` (ETag) em segundos | Padrão 5; 0 = lê o banco a cada requisição. |
| `LOG_LEVEL` | Nível de log | Padrão `INFO` |
| `RESTCOUNTRIES_API_KEY` | Chave do REST Countries | Só o ETL de referência usa |
| `WIKIDATA_CONTACT` | E-mail ou site para o User-Agent da Wikidata | Exigido pela política da Wikimedia; só o ETL usa |
| `WEB_PUBLIC_DATA_DIR` | Pasta pública do front | Para copiar a geometria (Fase 3) |

**Supabase:** use o *Session pooler* (porta 5432, usuário `postgres.<ref>`). O host direto (`db.<ref>.supabase.co`) é só IPv6 e falha em muitas redes. Evite o modo *transaction* (porta 6543): costuma quebrar prepared statements do psycopg 3.

## Comandos

| Comando | O que faz |
|---|---|
| `make dev` | Sobe a API com reload |
| `make test` | Roda os testes |
| `make lint` | ruff |
| `make typecheck` | mypy (strict) |
| `make openapi` | Gera `openapi.generated.json` |
| `make db-up` | Sobe o Postgres local |
| `make migrate` | Aplica as migrations |
| `make etl-restcountries` | Baixa fatos de países (ver ETL) |

Ainda por criar (ver TODO): `seed`, `import`, `etl-modern-geometry`, `etl-snapshots`, `etl-link-snapshots`, `sync-geometry`.

## Contrato da API

O contrato oficial é [contract/CONTRACT.md](contract/CONTRACT.md) e é **congelado**: o front mantém uma cópia idêntica. Problema no contrato? Registre em `contract/CHANGE_REQUESTS.md` (o quê, por quê, correção proposta) e avise; não contorne em silêncio. Como o contrato se mapeia ao código: [docs/CONTRACT_NOTES.md](docs/CONTRACT_NOTES.md).

Endpoints (todos GET, prefixo `/v1`):

| Rota | Retorno |
|---|---|
| `/health` | `{status, db}` |
| `/meta` | versão dos dados, intervalo de anos, anos de snapshot, contagens |
| `/countries` · `/countries/{iso2}` | lista e detalhe de países modernos |
| `/polities?year=&limit=&offset=` | entidades (filtráveis por ano) |
| `/polities/{id}` | detalhe com nomes, sucessores, linha do tempo, fontes |
| `/snapshots` · `/snapshots/nearest?year=` · `/snapshots/{year}/links` | mapas históricos e mapeamento |
| `/search?q=&limit=` | busca (países e entidades) |

Erros: `application/problem+json` com `{type, title, status, detail}` (404 id/ano desconhecido, 422 parâmetro inválido). Geometria **não** é servida pela API; o front a lê de `/data/...`.

Cabeçalhos de cache (`ETag`, `X-Data-Version`, `Cache-Control`, 304) estão previstos no contrato e **ainda não implementados** (Fase 4).

## Modelo de dados

Tabelas (PostgreSQL, com CHECKs e índices; definidas em [src/atlas_api/db/models.py](src/atlas_api/db/models.py)):

| Tabela | Conteúdo |
|---|---|
| `polities` | Entidades políticas: tipo, início/fim, precisão, ISO2, regime, resumo, bloco de política atual |
| `polity_names` | Períodos de nome (ex.: Constantinopla → Istambul) |
| `succession` | Ligações predecessor → sucessor (`renamed`, `succeeded`, `split`, `merged`, `absorbed`, `conquered`) |
| `events` · `event_sources` · `sources` | Linha do tempo com precisão de data e fontes citáveis |
| `snapshots` · `snapshot_links` | Mapas históricos e o mapeamento (ano, nome do polígono) → entidade, com status `curated`/`auto`/`unresolved` |
| `country_facts` | Fatos de países modernos (capital, população, idiomas...) vindos da Wikidata (CC0) |
| `meta` | `data_version` (hash do conteúdo) e `generated_at` |

O **único escritor** do banco será o comando de importação de conteúdo (`import-content`, idempotente, em uma transação). Não há endpoints de escrita nem autenticação na v1.

## Regras do "ano Y"

- **Sem ano zero:** 1 a.C. = `-1`, 1 d.C. = `1`. A distância entre anos deve pular o zero (documentar no helper `year_distance`).
- **Existe no ano Y** ⇔ `start_year <= Y` e (`end_year` é nulo ou `Y <= end_year`). Os dois extremos são **inclusivos**; `end_year` é o último ano de existência.
- **Nome no ano Y:** o período de `polity_names` que cobre Y; se nenhum, `polities.name`.
- **Snapshot mais próximo:** menor distância absoluta; empate vai para o **anterior**; sempre devolve `distance_years`.
- **`has_content`:** a entidade tem resumo ou ao menos um evento.
- Linhas do tempo ordenadas por `year_start` e depois `id`. Sucessão **acíclica**.
- **Nunca inventar dado:** ausente = `null`.

## ETL

CLI separada em [etl/](etl/), usa o grupo de dependências `etl` e lê o `.env` sozinha.

> **Não usado para o banco; mantido só para referência.** Os termos do REST Countries (Seção 5 e 6) proíbem guardar os dados além de 3 dias e agregá-los em produto downstream. Os fatos persistentes virão da Wikidata (CC0) e do World Bank (Fase 2).

**REST Countries** (referência; `make etl-restcountries` → `data_out/facts.json`):
- Usa o endpoint de lista paginado (≈3 requisições para todos os países) e cacheia as respostas brutas em `etl_cache/` por até 3 dias.
- Plano Free: 1.000 req/mês, 20 req/10 s, uso não comercial.
- Os termos limitam o cache a 3 dias, exigem atribuição ("REST Countries" com link) e restringem re-expor os dados como API/dataset próprio. **Avalie isso antes do deploy público** (ver [docs/TODO.md](docs/TODO.md)).
- O API não informa o ano da população: `population_year` fica `null`.

**Wikidata** (`make etl-wikidata` → `data_out/wikidata.json`): uma consulta SPARQL pequena por propriedade, uma de cada vez, com User-Agent descritivo (contato em `WIKIDATA_CONTACT`) e respostas brutas em `etl_cache/wikidata/` com `retrieved_at`. Licença CC0; a Wikidata pede, sem exigir, a menção "Data from Wikidata".

**v1.2 (parte A, specs 009/015/017/019)** — todos gravam em `data_out/` e são lidos por `import-facts`:
- `python -m etl wikidata-languages [BR IN ...]` → `languages.json` (idiomas falados; com ISO2 = amostra em `languages_sample.json`). Famílias e regiões nativas em `content/language_families.yaml` (rascunho, revisão humana pendente).
- `python -m etl worldbank` → `worldbank.json` (23 indicadores WDI desde 1990, arquivo bulk CSV por indicador, CC BY 4.0) e depois `python -m etl undp` → `undp.json` (IDH e anos médios de estudo, CC BY 3.0 IGO).
- `python -m etl fx` → `fx.json` (câmbio BCE diário desde 1999 via Frankfurter + exchange-api semanal desde 2024-03 para moedas fora do BCE, fonte secundária). Rodar de novo = só o ano corrente e a data `latest` são rebaixados.
- **Imagens (spec 019):** a Commons pede para evitar hotlink. Com `IMAGE_BUCKET_URL` (`https://<ref>.supabase.co/storage/v1`) e `SUPABASE_SERVICE_KEY` no ambiente, `wikidata-leaders` e `pantheon` copiam cada miniatura (320px) para o bucket público `atlas-images` (crie o bucket como público antes) e `image.url` passa a apontar para lá; uploads já feitos ficam em `etl_cache/.../mirrored.json`. **Sem as duas variáveis o passo é pulado** e a URL continua sendo a da Commons (fallback). A chave de serviço nunca vai para o git nem para o processo da API.

Planejados: snapshots históricos e proposta de links para curadoria. A geometria **moderna** é do repositório web; aqui só entram os snapshots históricos.

## Seed dos países (política da opção A)

Todo país moderno precisa de uma linha em `polities` (`country_facts.iso2` aponta para ela e `start_year` é obrigatório). Os 197 arquivos em `content/polities/` são **gerados** por `scripts/seed_countries.py` a partir da Wikidata, com:

- `start_year: 1946` e `start_precision: century` = **placeholder, data de formação ainda não curada**. É posterior a 1945 de propósito, para os países modernos não aparecerem em `/polities?year=` de anos anteriores; em troca, países formados depois de 1946 aparecem um pouco cedo. Para curar um país, edite o YAML.
- `type: other` (não curado) e ids em português sem acento, exceto os 8 ids do contrato (`austria`, `brazil`, `germany`, ...).
- Alemanha, Iugoslávia/Sérvia e nomes de cidades **ainda dependem da sua decisão**: hoje `germany` e `serbia` são só placeholders, sem sucessão.
- Os 5 arquivos de `seed_legacy/` viram eventos com `# TODO verify` e sem fontes (texto escrito por IA de memória, **não verificado**); o resumo do importador conta esses eventos.

Comandos (banco local): `python -m atlas_api.cli import-content` e `python -m atlas_api.cli import-facts` (lê `data_out/wikidata.json` e, se existirem, `leaders`, `pantheon`, `languages`, `worldbank`, `undp`, `fx`; muda o `data_version`, logo o ETag).

## Como adicionar conteúdo (planejado)

O fluxo abaixo vale a partir da Fase 1, quando o importador existir:

- **Entidade:** novo arquivo `content/polities/<id>.yaml` (campos, períodos de nome, eventos com precisão e ids de fontes, bloco de política). Fontes em `content/sources.yaml`.
- **Sucessão:** nova linha em `content/succession.yaml` (o importador rejeita ciclos).
- **Link de snapshot:** linha em `content/snapshot_links.csv` (`snapshot_year,source_name,polity_id,status,note`). Linhas `curated` nunca são sobrescritas pelo ETL.
- Depois rode `python -m atlas_api.cli import-content`.

Datas incertas devem ganhar `# TODO verify` em vez de palpite.

## Deploy (planejado)

Alvo: FastAPI Cloud (`fastapi deploy`) + Supabase Postgres, na mesma região. Pontos a confirmar na doc do FastAPI Cloud: variáveis/segredos, região, formato do `.fastapicloudignore`. O plano Hobby faz *scale-to-zero*, então a primeira requisição depois de ociosidade pode ser lenta. Runbook será escrito na Fase 4.

## Limitações conhecidas

- Fronteiras históricas são **aproximadas** e os snapshots **não são contínuos** (só alguns anos existem).
- Fronteiras disputadas (Kosovo, Taiwan, Crimeia) exigem escolha política; a escolha feita será documentada aqui quando o conteúdo for curado. `XK` é o código não oficial do Kosovo.
- Modelar sucessões (Alemanha, Iugoslávia, nomes de cidades) força decisões políticas; elas dependem de aprovação e serão listadas.
- Hoje os dados são **placeholders**, não história curada.

## Licenças e atribuições

### Fontes de dados e atribuição que o front deve mostrar

| Fonte | Uso | Licença (lida em 2026-11-11) | Atribuição |
|---|---|---|---|
| [Wikidata](https://www.wikidata.org/) | fatos dos países | CC0 (dados estruturados) | Não exigida; pedida: "Data from Wikidata" |
| [Flagpedia / flagcdn.com](https://flagpedia.net/) | `flag_url` | "in the public domain and can be used freely without restriction" (termos do site) | Backlink para flagpedia.net apreciado, não exigido |
| World Bank Indicators | `indicators` (Fase 2, ainda não feito) | CC BY 4.0 (página de datasets, "Last Updated: Mar 23, 2018") | Obrigatória: "The World Bank: nome do dataset: fonte" |
| historical-basemaps | snapshots (Fase 3) | GPL-3.0, a avaliar | A definir |
| REST Countries | **não usado** no banco | termos proíbem reter além de 3 dias | n/a |

`content/official_names_pt.yaml` tem nomes oficiais traduzidos pelo assistente, **não verificados**. `memberships` traz só a ONU (a Wikidata é incompleta para as demais organizações).

O código está sob a licença do arquivo [LICENSE](LICENSE). Os mapas do historical-basemaps são GPL-3.0; um `NOTICE.md` com atribuição e as implicações será adicionado na Fase 3 (questão a avaliar, não decidida).
