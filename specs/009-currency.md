# 009 — Moeda: cotações e PPP
Status: draft | Contrato: v1.2 | Web: atlas-web/specs/009-currency.md

## Dados
| Fonte | Cobertura | Chave | Licença/termos (a confirmar) |
|---|---|---|---|
| BCE via Frankfurter (api.frankfurter.app) | ~30 moedas, diária, desde 1999 | não | dados do BCE, reuso com citação |
| fawazahmed0/exchange-api (jsDelivr) | 200+ moedas, diária | não | CC0; origem dos números pouco documentada |
| World Bank `PA.NUS.PPP` | quase todos os países, anual | não | CC BY 4.0 (ETL do World Bank já existe) |
Recomendado: BCE como principal; a segunda só para moedas fora do BCE, marcada como fonte secundária.
Moedas de cada país já existem (`currencies` do Wikidata). Atenção: FR lista "franco CFP" (territórios ultramarinos), ver CR do web.

## Contract delta
```
GET /v1/currencies/{code}                       -> { code, name, symbol, countries: string[], rates: { date, base, items: [{ code, rate }] }|null,
                                                     ppp: { value, year, source_id }|null, sources: Source[] }
GET /v1/currencies/{code}/history?vs=&from=&to= -> { base, vs, items: [{ date, rate }], source: Source }
`code` = ISO 4217 (^[A-Z]{3}$), senão 422.
```

## Design
- Sem tabela de cotações: cliente HTTP na API com cache em memória TTL 12 h (`functools`/dict com timestamp; sem lib nova).
  Reinício = busca de novo. Timeout 5 s; upstream fora = `rates: null` (nunca 500).
- O processo da API passa a chamar upstream em tempo de requisição: isso é novo neste repo; o cliente fica em
  `src/atlas_api/upstream/` e usa só `httpx` (verificar se já é dependência do grupo principal; senão `urllib`).
- PPP: indicador novo no ETL do World Bank, gravado por `import-facts`.

## Tarefas
- [ ] ler e citar termos; cliente + cache; endpoints; testes com respostas gravadas
- [ ] PA.NUS.PPP no ETL do World Bank
