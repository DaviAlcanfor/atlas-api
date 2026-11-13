# Atlas API

**API REST somente leitura com fatos, história, política e economia dos países do mundo, reunidos de fontes abertas, com a fonte e a licença de cada dado.**

[Documentação interativa](https://atlas-api.fastapicloud.dev/docs) · [Site do Atlas](https://atlas-web-ruddy.vercel.app) · [Repositório do site](https://github.com/DaviAlcanfor/atlas-web)

```bash
curl https://atlas-api.fastapicloud.dev/v1/countries/BR/subdivisions
```

```json
{
  "items": [
    {
      "wikidata_id": "Q175", "code": "BR-SP", "name": "São Paulo", "capital": "São Paulo",
      "area_km2": 248209.4, "population": { "value": 46179008, "year": 2026 },
      "flag": { "url": "https://…/Bandeira_do_estado_de_São_Paulo.svg.png", "credit": "… / Wikimedia Commons", "license": "Public domain" }
    }
  ],
  "sources": [{ "id": "wikidata", "title": "Wikidata", "license": "CC0 1.0", "…": "…" }]
}
```

## O que a API oferece

- **197 países e 3.754 estados e províncias:** capital, população com ano, área, regime político, idiomas, moedas, organizações, bandeira e código ISO.
- **Política:** governantes atuais e anteriores (10.766 mandatos) e um glossário de formas de governo.
- **Como vive o povo:** 25 indicadores (23 do Banco Mundial, 2 do PNUD) (expectativa de vida, IDH, renda, escolaridade...), com a posição do país no ranking mundial e a média da região.
- **Economia e câmbio:** PIB, inflação, comércio e cotações diárias desde 1999, com comparação entre países.
- **História:** resumo e períodos condensados da Wikipédia (190 países), marcos curados e linhagem entre entidades políticas.
- **Pessoas importantes:** as figuras mais conhecidas de cada país, segundo o Pantheon (7.749 pessoas).

Três regras valem para todos os endpoints:
- **Nada é inventado:** dado ausente é `null`.
- **Toda resposta traz `sources`,** com título, URL, licença e data de coleta.
- **Texto não verificado é marcado como tal.**

## Endpoints

Todos são `GET`, com prefixo `/v1`. O contrato completo está em [`contract/CONTRACT.md`](contract/CONTRACT.md), e a referência navegável em [`/docs`](https://atlas-api.fastapicloud.dev/docs).

| Rota | Retorna |
|---|---|
| `/countries` | lista de países (nome, região, regime, capitais com coordenadas, marcador de micro-estado) |
| `/countries/{iso2}` | detalhe do país: fatos, idiomas falados por status, moedas, política atual, marcos, pistas de GeoGuessr |
| `/countries/{iso2}/profile` | indicadores sociais com ranking mundial e média regional; composição religiosa e étnica |
| `/countries/{iso2}/economy` | indicadores econômicos com série histórica |
| `/countries/{iso2}/leaders?role=` | chefes de Estado e de governo, com foto, partido e mandato |
| `/countries/{iso2}/people?domain=&limit=` | pessoas importantes por área (política, ciência, artes, esportes...) |
| `/countries/{iso2}/history` | resumo da história e períodos com datas |
| `/countries/{iso2}/subdivisions` | estados e províncias com bandeira |
| `/economy/compare?countries=&ids=` | 2 a 5 países lado a lado |
| `/currencies/{code}` · `/currencies/{code}/history?vs=&from=&to=` | cotações atuais, variação e volatilidade · histórico diário (semanal em janelas longas) |
| `/glossary` · `/glossary/{id}` | verbetes (formas de governo, regiões, organizações) com exemplos |
| `/polities?year=` · `/polities/{id}` | entidades políticas (inclusive extintas), com nomes ao longo do tempo e sucessão |
| `/snapshots` · `/snapshots/nearest?year=` · `/snapshots/{year}/links` | mapas históricos (base da futura viagem no tempo) |
| `/search?q=` · `/meta` · `/health` | busca sem acento · versão dos dados · estado do serviço |

**Erros:** `application/problem+json` (`404` para id ou ano desconhecido, `422` para parâmetro inválido, `503` com o banco indisponível).

**Cache:** toda resposta leva `ETag` (derivado da versão dos dados), `X-Data-Version` e `Cache-Control: public, max-age=300, stale-while-revalidate=86400`. Um `If-None-Match` igual recebe `304`.

## Arquitetura

```mermaid
flowchart LR
  subgraph Fontes abertas
    WD[Wikidata] --- WB[Banco Mundial] --- UN[PNUD] --- WP[Wikipédia] --- ECB[BCE] --- PT[Pantheon] --- CM[Commons]
  end
  Fontes -->|"python -m etl …"<br/>cache + polidez| OUT[data_out/*.json]
  CUR[content/*.yaml<br/>curadoria] --> IMP
  OUT --> IMP["atlas_api.cli import-content<br/>import-facts"]
  IMP -->|uma transação| DB[(PostgreSQL)]
  DB --> API[FastAPI<br/>somente leitura]
  API --> WEB[Atlas web]
```

- **ETL separado da API.** O ETL (`etl/`) tem dependências próprias e nunca é importado pelo processo da API, que fica leve e sobe rápido. Cada fonte tem um módulo que respeita as regras de uso dela (User-Agent com contato, uma consulta por vez, cache das respostas brutas) e grava um JSON em `data_out/`.
- **Um único escritor.** O banco só é escrito pelos comandos `import-content` (curadoria em `content/`) e `import-facts` (saídas do ETL), sempre numa transação. A API não tem rotas de escrita. Cada importação gera uma nova versão dos dados, que vira o `ETag`.
- **Migrações automáticas.** Ao subir, a API leva o schema ao `head` do Alembic, com um advisory lock do Postgres para réplicas que sobem juntas. Por isso as migrações são sempre aditivas. Os dados continuam sendo importados à parte.
- **Resiliência.** Cada processo tem um pool de conexões pequeno e limitado, com espera curta: num pico, a API responde `503` rápido em vez de travar. Se o banco estiver fora na subida, a API sobe mesmo assim.

## Stack

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 (psycopg 3) · Alembic · PostgreSQL (Supabase em produção) · pytest com Postgres real · ruff · mypy (strict) · hospedagem no FastAPI Cloud

## Rodando localmente

Pré-requisitos: Python 3.12 ou 3.13, [uv](https://docs.astral.sh/uv/) e Docker.

```bash
uv sync                                   # dependências da API e de desenvolvimento
cp .env.example .env                      # ajuste os valores (tabela abaixo)
docker compose up -d --wait               # Postgres local
uv run alembic upgrade head               # schema (a API também faz isso ao subir)
uv run python -m atlas_api.cli import-content   # curadoria de content/
uv run uvicorn atlas_api.main:app --reload --app-dir src   # http://localhost:8000/docs
```

Para preencher os fatos, rode o ETL e depois o `import-facts` (seção abaixo).

| Comando | O que faz |
|---|---|
| `make dev` | API com reload |
| `make test` | pytest contra um Postgres local descartável (cria `atlas_test`) |
| `make lint` · `make typecheck` | ruff · mypy strict |
| `make openapi` | gera `openapi.generated.json`, de onde o site gera os tipos |
| `make db-up` · `make migrate` | Postgres local · migrações manuais |

> **Windows:** sem `make`, use a linha `uv run …` de cada alvo do [Makefile](Makefile). Se o OneDrive travar o `.venv`, chame os executáveis direto (`.venv/Scripts/python.exe`).

### Variáveis de ambiente

Segredos só por variável de ambiente ou `.env`, que o git ignora.

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | Postgres (`postgresql+psycopg://usuário:senha@host:porta/banco`; codifique caracteres especiais da senha) |
| `CORS_ORIGINS` | origens permitidas, separadas por vírgula |
| `AUTO_MIGRATE` | `false` desliga a migração na subida (padrão `true`) |
| `DB_POOL_SIZE` · `DB_MAX_OVERFLOW` · `DB_POOL_TIMEOUT` | pool por processo (padrão 5 · 2 · 3 s). Total = processos × (size + overflow), abaixo do limite do pooler |
| `DATA_VERSION_TTL` | segundos de cache da versão dos dados (padrão 5) |
| `ATLAS_DB_PORT` | porta local do Postgres no `docker compose` (padrão 5432) |
| `WIKIDATA_CONTACT` | e-mail ou site para o User-Agent da Wikimedia (só o ETL) |
| `IMAGE_BUCKET_URL` · `SUPABASE_SERVICE_KEY` | espelham fotos e bandeiras do Commons num bucket público (só o ETL; sem elas, as URLs apontam para o Commons) |
| `ADMIN1_DIR` | pasta com os polígonos de estados do site (padrão `../geo/public/data/admin1`) |

**Supabase:** use o *Session pooler* (porta 5432). O host direto é só IPv6, e o modo *transaction* (porta 6543) quebra prepared statements do psycopg 3.

## Dados: ETL e importação

```bash
python -m etl wikidata                # fatos dos países            -> data_out/wikidata.json
python -m etl wikidata-leaders        # governantes e fotos         -> leaders.json
python -m etl wikidata-languages      # idiomas por status          -> languages.json
python -m etl wikidata-subdivisions   # estados e bandeiras         -> subdivisions.json
python -m etl wikipedia-history       # resumos de história         -> history.json
python -m etl pantheon                # pessoas importantes         -> pantheon.json
python -m etl worldbank && python -m etl undp   # indicadores       -> worldbank.json, undp.json
python -m etl fx                      # câmbio diário               -> fx.json
python -m atlas_api.cli import-facts  # lê o que existir em data_out/ e grava numa transação
```

Os comandos aceitam códigos ISO2 para uma amostra (`python -m etl wikipedia-history BR JP`) e `--refresh` para ignorar o cache. Antes de integrar uma fonte nova, os termos de uso e a licença dela são lidos e citados na spec correspondente. Esse registro está em [`specs/`](specs/README.md).

**Publicar dados em produção:** rode `import-facts` com `DATABASE_URL` apontando para o banco de produção, a partir de um checkout do código que está no ar. O modelo está em [`scripts/prod-migrate-example.ps1`](scripts/prod-migrate-example.ps1).

## Modelo de dados

| Tabelas | Conteúdo |
|---|---|
| `polities` · `polity_names` · `succession` | entidades políticas, nomes ao longo do tempo e sucessão (renomeada, sucedida, dividida, unida, absorvida, conquistada) |
| `events` · `sources` · `event_sources` | marcos com precisão de data e fontes citáveis |
| `country_facts` · `capitals` · `country_languages` · `compositions` | fatos dos países |
| `leaders` · `people` | governantes e pessoas importantes |
| `indicator_defs` · `indicators` · `indicator_latest` · `indicator_stats` | séries e estatísticas pré-calculadas (ranking, mediana mundial, média regional) |
| `fx_rates` · `currency_stats` | câmbio |
| `country_history` · `history_periods` · `subdivisions` · `glossary_terms` | história condensada, estados e glossário |
| `snapshots` · `snapshot_links` · `meta` | mapas históricos e versão dos dados |

**Regras de tempo:**
- Não existe ano zero: 1 a.C. é `-1`.
- Uma entidade existe no ano Y quando `start_year ≤ Y ≤ end_year`, com fim nulo significando "até hoje".
- O nome no ano Y é o do período que cobre Y.
- O snapshot mais próximo desempata para o anterior.

## Qualidade

- **Testes:** cerca de 90 testes de ponta a ponta contra um Postgres real, com os dados reais de `content/` e `data_out/`.
- **Código:** mypy strict e ruff.
- **Contrato:** o contrato é congelado e espelhado no site. Mudanças entram por change request em [`contract/CHANGE_REQUESTS.md`](contract/CHANGE_REQUESTS.md), e o OpenAPI gerado alimenta a checagem de tipos do front.
- **Specs:** cada funcionalidade tem uma spec em [`specs/`](specs/README.md), com o mesmo número no repositório do site.

## Limitações conhecidas

- **Governadores** ficaram de fora dos estados: no Wikidata eles estão desatualizados.
- **Regime político** vem de um seed antigo ainda não verificado. O glossário e os textos de `content/` são rascunhos à espera de revisão humana.
- **Datas de formação** dos países modernos são um placeholder (1946) até a curadoria.
- **Mapas históricos** (viagem no tempo) ainda não foram importados; a fonte escolhida é o [Cliopatria](https://github.com/Seshat-Global-History-Databank/cliopatria) (CC BY 4.0).

## Fontes e licenças

| Fonte | Uso | Licença | Atribuição |
|---|---|---|---|
| [Wikidata](https://www.wikidata.org/) | fatos, governantes, idiomas, estados | CC0 | pedida, não exigida |
| [Wikimedia Commons](https://commons.wikimedia.org/) | fotos e bandeiras de estados | por arquivo (autor e licença em cada `image`/`flag`) | obrigatória, por arquivo |
| [Wikipédia](https://pt.wikipedia.org/) | resumos de história | CC BY-SA 4.0 | título e link da revisão em `sources` |
| [Banco Mundial (WDI)](https://data.worldbank.org/) | indicadores | CC BY 4.0 | obrigatória |
| [PNUD (HDR)](https://hdr.undp.org/) | IDH, anos de estudo | CC BY 3.0 IGO | obrigatória |
| [Banco Central Europeu](https://www.ecb.europa.eu/) via Frankfurter · exchange-api | câmbio | reuso livre com citação | fonte em `source` |
| [Pantheon](https://pantheon.world/) | pessoas importantes | CC BY-SA 4.0 | obrigatória |
| [flagcdn / Flagpedia](https://flagpedia.net/) | bandeiras de países | domínio público | não exigida |

O código está sob a licença [MIT](LICENSE).
