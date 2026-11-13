# 009 - Moeda, câmbio e economia comparável
Status: done (local, não publicado; contrato = CR-003) | Contrato: v1.2 | Web: atlas-web/specs/009-currency.md | Executor: Opus (ETL/estatísticas), Sonnet (endpoints)

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

## Termos lidos e citados (2026-11-12)
- **Frankfurter** (https://frankfurter.dev, `/license/`): código "open source under the MIT License"; dados: "Frankfurter doesn't own the
  rates ... If a provider publishes terms of use, they apply"; "There are no quotas. Requests are rate-limited to prevent abuse".
  API v2: `GET https://api.frankfurter.dev/v2/rates?from=&to=&base=EUR&providers=ecb` (lista de `{date, base, quote, rate}`); o
  provedor ECB começa em 1999-01-04 (`/v2/providers/ecb`).
- **BCE** (https://www.ecb.europa.eu/services/disclaimer/html/index.en.html): "users of this website may make free use of the information
  obtained directly from it" desde que "it must appear accurately and the ECB must be cited as the source" e "If the information is
  modified by the user (e.g. ... calculation of growth rates) ... this must be stated explicitly" → o título do `Source` `ecb` diz
  "cross rates and statistics calculated by Atlas".
- **fawazahmed0/exchange-api** (https://github.com/fawazahmed0/exchange-api): "CC0-1.0", "No Rate limits", "Please include Fallback
  mechanism" (usamos `<data>.currency-api.pages.dev` como fallback do jsDelivr). Arquivos por data só existem **desde 2024-03-02**, um
  request por data: pegamos **uma data por semana (quartas) + `latest`**. Marcado como fonte secundária (`exchange-api`).
- World Bank WDI: CC BY 4.0 (ver spec 015; lido via Data360 porque api.worldbank.org estava fora do ar).

## O que foi feito
- `python -m etl fx` → `data_out/fx.json` (`[date, code, rate, source_id]`, 1 EUR = rate) → `fx_rates` (migração 0010). BCE ganha
  quando publica a moeda (moedas que o BCE ainda publica na última data); o resto vem do exchange-api, só códigos usados pelos nossos países.
  Rodar de novo rebaixa só o ano corrente e `latest` (incremental).
- `currency_stats` no import: valor de 1 unidade em USD (EUR para o USD); variação 1a/5a (ponto mais próximo anterior, até 14 dias),
  volatilidade = desvio padrão dos retornos log do último ano × √(nº de retornos no ano) (anualiza diário ou semanal), maior queda do ano.
- Cross rates em SQL (self-join de `fx_rates` por data). Endpoints `/v1/currencies/{code}`, `/history` (semanal acima de 2 anos),
  `/v1/countries/{iso2}/economy` (10 ids, série de 20 anos), `/v1/economy/compare` — texto exato em CR-003.
- "FR lista o franco CFP": a moeda principal não é escolhida pela API; `countries` de cada moeda lista quem usa (P38), `XPF` tem cotação.

## Cobertura (banco local, 2026-11-12)
- `fx_rates`: 287.427 linhas; BCE 45 moedas (1999-01-04 → 2026-11-11, inclui legadas como GRD); exchange-api 119 moedas (2024-03-06 →
  2026-11-12, semanal). `currency_stats`: 159 moedas; `change_1y` 158, `volatility_1y` 159, `change_5y` só 40 (as do BCE: o secundário
  só tem 2,7 anos).
- Moedas dos países (Wikidata P38): 153 códigos, **148 com cotação**; **197/197 países** têm ao menos uma moeda com cotação. Sem cotação:
  BA:BAD, CZ:"203", PL:PLZ, ZW:ZWN, ZW:ZWR (moedas antigas/códigos errados que a Wikidata ainda lista como atuais; a correção é na Wikidata).
- Exemplo BRL (vs USD, 2026-11-11): 1a −4,9%, 5a −2,7%, volatilidade 15,2%, maior queda −12,3%.
- Economia (países com valor): PIB 194, PIB pc PPC 191, crescimento 194, inflação 186, desemprego 179, **dívida do governo 109** (o WDI
  só tem para metade), conta corrente 189, reservas 175, Gini 171, PPC 192. Sem dados: TW e VA (fora do Banco Mundial), KP quase nada.

## Tarefas
- [x] ler termos BCE/Frankfurter/exchange-api; citar aqui
- [x] `etl fx` + tabela + stats; endpoints de moeda; testes (`tests/test_v12_api.py` no banco real, `tests/test_v12_build.py` sem rede)
- [x] indicadores WDI novos + tabela `indicators`; endpoints de economia e comparação; testes
- [x] agendar `etl fx` diário: `.github/workflows/fx-daily.yml` (dias úteis, 15:30 UTC), `atlas_api.cli currency-codes` + `etl fx` + `import-fx` (só câmbio; versão dos dados ganha a parte "fx"). Precisa do secret `DATABASE_URL` no GitHub
