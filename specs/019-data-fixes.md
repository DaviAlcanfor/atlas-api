# 019 - Correções de dados encontradas na fase B
Status: done (local, branch `feat/v1.2-data`; não publicado) | Contrato: não muda (só o texto de `Images`, ver CR-003) | Executor: Sonnet

## Problemas
1. **ETag velho depois de importar fatos**: `data_version` só faz hash de `content/`. Depois de `import-facts` (Wikidata, World Bank,
   líderes, pessoas), clientes recebem 304 com dados antigos.
   Correção: `data_version` = hash de `content/` + `max(updated_at)` das tabelas de fatos (ou um contador gravado por cada import numa tabela
   `meta(key, value)`). Teste: import-facts com um valor alterado muda o ETag de `/v1/countries/{iso2}`.
2. **Dinamarca (DK) ausente** dos 196 países semeados (o import pula DK). Investigar o seed (`scripts/seed_countries.py`) e a query
   `STATE` do Wikidata (o item da Dinamarca pode ter P31 diferente de Q3624078 por causa do Reino da Dinamarca). Teste: DK presente.
3. **Hotlink de imagens do Wikimedia** (governantes, pessoas): o Commons pede para evitar hotlink. Decisão aprovada: copiar as miniaturas
   (320px) para um bucket (Supabase Storage, público) no ETL e servir de lá; `image.url` passa a apontar para o bucket.
4. **Países com várias capitais** (spec 005 fase 2): ZA, BO, NL... tabela `capitals`.

## O que foi feito (2026-11-12)
1. `importer.set_version(part, digest)`: `meta.content_version` (hash do `content/`, como antes) + `meta.facts_version` (hash dos bytes de
   todos os `data_out/*.json` lidos pelo `import-facts`) → `data_version` = hash dos dois. Mesmo arquivo de novo = mesmo ETag; um valor
   alterado = ETag novo. Teste `test_import_facts_changes_data_version_and_etag` (banco real, cliente HTTP real, `If-None-Match` antigo → 200).
2. **Causa:** a ISO 3166 "DK" está no item Q35 ("Dinamarca", sem Groenlândia/Feroé, que têm códigos ISO próprios, igual ao DNK do World
   Bank), e Q35 é P31 "país autônomo dentro do Reino da Dinamarca", não Q3624078. O Estado soberano (Q756617, membro da ONU) não tem P297.
   **Correção:** `STATE` = `{ P31 Q3624078 } UNION { VALUES ?c { wd:Q35 } }` e associações (ONU) lidas de Q756617 (`MEMBERSHIP_FROM`).
   `content/polities/dinamarca.yaml` (mesmo formato do seed) e `content/official_names_pt.yaml` (Reino da Dinamarca). Agora são
   **197 países**: os 193 da ONU + VA, PS, XK, TW. Todos os ETLs (wikidata, leaders, pantheon, languages, worldbank, undp) foram rodados
   de novo com DK: líderes 10.766 mandatos em 197/197 países (com foto 6.666, com partido 4.981); Pantheon 7.749 pessoas em
   197 países (com foto 6.360). DK: capital Copenhague, regime monarquia constitucional, ONU.
3. `etl/wikidata/leaders.mirror_images` (usado por `wikidata-leaders` e `pantheon`): com `IMAGE_BUCKET_URL`
   (`https://<ref>.supabase.co/storage/v1`) e `SUPABASE_SERVICE_KEY`, baixa cada miniatura e faz upload (upsert) para o bucket público
   `atlas-images`, nome = sha256 da URL de origem; `image.url` = `<IMAGE_BUCKET_URL>/object/public/atlas-images/<arquivo>`; uploads feitos ficam
   em `mirrored.json` no cache. **Sem as duas variáveis o passo é pulado e o hotlink da Commons continua (fallback).** Não foi executado:
   este ambiente não tem credenciais do Supabase. Para ativar: criar o bucket `atlas-images` público, definir as duas variáveis só no
   ambiente do ETL (nunca no git nem na API) e rodar `python -m etl wikidata-leaders` e `python -m etl pantheon`, depois `import-facts`.
   Testes com transporte HTTP falso (sem rede): pulado sem credenciais; com credenciais, 1 download + 1 upload e o 2º run usa o cache.
4. Migração 0007 `capitals(iso2, ord, name, lat, lng)`. ETL: todo P36 atual (sem P582, rank não-depreciado), preferido primeiro, depois por
   nome; um por nome. `capital` (v1.0) = o primeiro. `capital_coords` lista todos com coordenadas.
   Resultado (Wikidata 2026-11-12): 8 países com mais de uma capital: ZA (Bloemfontein, Cidade do Cabo, Pretória), BO (La Paz, Sucre),
   BJ (Porto Novo, Cotonu), LK (Colombo, Kotte), MY (Kuala Lumpur, Putrajaya), PS (Jerusalém Oriental, Ramallah), SZ (Lobamba, Mebabane),
   YE (Sana, Áden). **NL só tem Amsterdã**: Haia está com rank depreciado na Wikidata (não a incluímos). 197/197 com coordenadas.

## 5. Produção parou com ~48 GETs simultâneos (adicionado 2026-11-12)
Sintoma (dono): FastAPI Cloud + Supabase, a build do web disparou ~48 `GET /v1/countries/{iso2}` ao mesmo tempo; a API parou de responder,
inclusive `/v1/health` (Cloudflare 524 por dezenas de minutos), duas vezes. Com 4 simultâneos aguentou. Produção NÃO foi tocada.

**Causa raiz (reproduzida localmente):** o middleware de cache (`cache.add_cache_headers`, `async`) lia `meta.data_version` com uma chamada
SÍNCRONA ao banco dentro do event loop. Com o pool cheio (5 + 5 conexões, `pool_timeout` padrão de 30 s), essa chamada bloqueava o loop
inteiro esperando uma conexão; as conexões só voltam ao pool quando as rotas (no threadpool) terminam, e o término passa pelo loop
bloqueado. Resultado: cada requisição esperava até 30 s, em fila, e o loop congelado não atendia nem `/v1/health` (que também pegava
conexão do mesmo pool). Com o código antigo e pool de 3 conexões, 100 GETs locais: timeouts de 60 s no cliente e `/v1/health` sem
resposta em 10 s mesmo depois do pico, exatamente o sintoma de produção.

**Correção:**
- `cache.py`: a leitura do `data_version` roda numa thread (`anyio.to_thread`) e fica em cache por processo por `DATA_VERSION_TTL` s
  (padrão 5): metade das idas ao banco por requisição some e o loop nunca bloqueia.
- Pool limitado e espera curta, configuráveis por env: `DB_POOL_SIZE` (5), `DB_MAX_OVERFLOW` (2), `DB_POOL_TIMEOUT` (3 s). Sem conexão
  livre em 3 s → `sqlalchemy.exc.TimeoutError` → **503 problem+json** (handler já existente), em vez de fila infinita.
- `/v1/health` agora é `async`, não depende do pool da requisição: se o pool está todo em uso responde na hora `{"status":"ok","db":"error"}`;
  senão faz o `SELECT 1` numa thread com limitador próprio (2), então não espera atrás das 40 threads das rotas.
- Teste `test_saturated_pool_degrades_fast` (pool 1, conexão segurada: país → 503 em < 3 s, health → db "error"; ao soltar, volta a 200/ok).
- `scripts/load_test.py` (rajada de N GETs + health a cada 0,2 s numa conexão separada). Local, servidor com `DB_POOL_SIZE=3 DB_MAX_OVERFLOW=0`
  imitando um pooler pequeno: **48 GETs: todos 200 em 1,1 s, health máx. 0,18 s; 100: todos 200 em 3,7 s, health máx. 0,44 s; 200: todos 200
  em 7,7 s, health máx. 0,39 s.** PASS nos três.

**O que o dono deve conferir/mudar (fora do código):**
- `DATABASE_URL` de produção usa o pooler do Supabase em **modo sessão** (`aws-0-us-east-1.pooler.supabase.com:5432`): cada conexão do nosso
  pool ocupa uma conexão do Postgres enquanto existir. Conexões totais = nº de processos/réplicas no FastAPI Cloud × (`DB_POOL_SIZE` +
  `DB_MAX_OVERFLOW`) = 7 por processo. Deixe esse total abaixo do "Pool Size" mostrado em Supabase → Database → Settings → Connection pooling.
  Se preferir não pensar nisso: modo transação (porta 6543) multiplexa melhor, mas com psycopg 3 exige desligar prepared statements
  (`prepare_threshold=None`); não fiz essa troca (precisa testar contra o Supabase real).
- FastAPI Cloud: o CLI (`fastapi cloud --help`, `deploy --help`) não tem opção de workers/réplicas; não achei na doc pública como fixar.
  Se o painel mostrar mais de 1 réplica/worker, reduza `DB_POOL_SIZE` na mesma proporção (`fastapi cloud env set DB_POOL_SIZE 3 --app-id ...`).
- Do lado do web: o build não precisa de 196 GETs paralelos; limitar a ~8 simultâneos (ou usar `GET /v1/countries`, que já traz o resumo de
  todos) evita até os 503 rápidos.
- Depois do deploy, rodar `python scripts/load_test.py https://atlas-api.fastapicloud.dev 48` uma vez (é tráfego real de produção: só com o dono).

## Tarefas
- [x] 1 data_version + teste
- [x] 2 Dinamarca + teste
- [x] 3 cópia de imagens para Supabase Storage no ETL (bucket `atlas-images`), atrás de `IMAGE_BUCKET_URL` + `SUPABASE_SERVICE_KEY`; **falta rodar** com credenciais (dono)
- [x] 4 várias capitais
- [x] 5 API degrada com 503 rápido em vez de travar (pool limitado, health sem bloqueio, teste de carga); ajustes de produção = dono
