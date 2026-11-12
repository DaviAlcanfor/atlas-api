# 019 - Correções de dados encontradas na fase B
Status: approved | Contrato: não muda | Executor: Sonnet

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

## Tarefas
- [ ] 1 data_version + teste
- [ ] 2 Dinamarca + teste
- [ ] 3 cópia de imagens para Supabase Storage no ETL (bucket `atlas-images`)
- [ ] 4 várias capitais
