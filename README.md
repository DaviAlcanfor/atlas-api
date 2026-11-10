# Atlas API

API somente leitura que serve **países modernos**, **entidades políticas históricas** (impérios, reinos, estados extintos), suas **linhas do tempo** e o **mapeamento entre polígonos de mapas históricos e essas entidades**.

> **Status:** em construção (Fase 0 concluída; schema do banco escrito). As rotas hoje respondem com dados de exemplo (fixtures JSON). O que falta está em [docs/TODO.md](docs/TODO.md).

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
| `LOG_LEVEL` | Nível de log | Padrão `INFO` |
| `RESTCOUNTRIES_API_KEY` | Chave do REST Countries | Só o ETL usa |
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
| `country_facts` | Fatos de países modernos (capital, bandeira, população, idiomas...) vindos do REST Countries |
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

**REST Countries** (`make etl-restcountries` → `data_out/facts.json`):
- Usa o endpoint de lista paginado (≈3 requisições para todos os países) e cacheia as respostas brutas em `etl_cache/` por até 3 dias.
- Plano Free: 1.000 req/mês, 20 req/10 s, uso não comercial.
- Os termos limitam o cache a 3 dias, exigem atribuição ("REST Countries" com link) e restringem re-expor os dados como API/dataset próprio. **Avalie isso antes do deploy público** (ver [docs/TODO.md](docs/TODO.md)).
- O API não informa o ano da população: `population_year` fica `null`.

Planejados: geometria moderna (Natural Earth), snapshots históricos e proposta de links para curadoria.

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

O código está sob a licença do arquivo [LICENSE](LICENSE). Os mapas do historical-basemaps são GPL-3.0; um `NOTICE.md` com atribuição e as implicações será adicionado na Fase 3 (questão a avaliar, não decidida).
