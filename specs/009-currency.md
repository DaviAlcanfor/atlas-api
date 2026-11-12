# 009 - Moeda, câmbio e economia comparável
Status: approved | Contrato: v1.2 | Web: atlas-web/specs/009-currency.md | Executor: Opus (ETL/estatísticas), Sonnet (endpoints)

## Dados
| Uso | Fonte | Cobertura | Licença/termos (ler e citar antes de codar) |
|---|---|---|---|
| Cotações diárias + histórico | BCE via Frankfurter (api.frankfurter.app) | ~30 moedas, desde 1999 | dados do BCE, reuso com citação |
| Moedas fora do BCE | fawazahmed0/exchange-api (jsDelivr) | 200+ moedas, diária | CC0; marcar como "fonte secundária" |
| Economia | World Bank WDI (ETL já existe) | quase todos os países, anual | CC BY 4.0 |

Indicadores WDI: NY.GDP.MKTP.CD (PIB), NY.GDP.PCAP.PP.CD (PIB pc PPP), NY.GDP.MKTP.KD.ZG (crescimento), FP.CPI.TOTL.ZG (inflação),
SL.UEM.TOTL.ZS (desemprego), GC.DOD.TOTL.GD.ZS (dívida/PIB), BN.CAB.XOKA.GD.ZS (conta corrente/PIB), FI.RES.TOTL.CD (reservas),
SI.POV.GINI (Gini), PA.NUS.PPP (PPP). Série de 20 anos.

## Contract delta (v1.2)
```
GET /v1/currencies/{code}                       -> { code, name, symbol, countries, rates: { date, base, items: [{ code, rate }] }|null,
                                                     stats: { change_1y, change_5y, volatility_1y, max_drawdown_1y }|null, sources }
GET /v1/currencies/{code}/history?vs=&from=&to= -> { base, vs: string[], items: [{ date, rates: { [code]: number } }], source }
                                                     vs: até 4 códigos; janela máx. 30 anos; pontos reduzidos a semanal acima de 2 anos
GET /v1/countries/{iso2}/economy                -> { indicators: [{ id, label, unit, value, year, source_id, series: [{ year, value }] }], sources }
GET /v1/economy/compare?countries=&ids=         -> { countries, indicators: [{ id, label, unit, values: { [iso2]: { value, year }|null } }], sources }
                                                     countries: 2-5 ISO2; ids opcional (padrão: todos)
`code` = ISO 4217 (^[A-Z]{3}$) senão 422.
```

## Design
- Cotações: tabela `fx_rates(date, base='EUR', code, rate, source)` preenchida por `python -m etl fx` (histórico completo uma vez, depois
  incremental diário no mesmo workflow agendado das notícias). Cross-rates calculados em SQL (A/B = EUR→B / EUR→A). Sem chamada a upstream
  em tempo de requisição.
- `stats` calculado no import: variação 1a/5a, volatilidade = desvio padrão anualizado dos retornos log diários (1 ano), maior queda (1 ano).
- Economia: indicadores novos no ETL do World Bank existente; tabela `indicators(country, id, year, value, source)` (é também a base da
  spec 012 / `observations`: usar o mesmo esquema para não duplicar).
- Atenção: FR lista "franco CFP" (territórios ultramarinos) junto com o euro; tratar moeda principal = a de rank preferido.

## Tarefas
- [ ] ler termos BCE/Frankfurter/exchange-api; citar aqui
- [ ] `etl fx` + tabela + stats; endpoints de moeda; testes com respostas gravadas
- [ ] indicadores WDI novos + tabela `indicators`; endpoints de economia e comparação; testes
