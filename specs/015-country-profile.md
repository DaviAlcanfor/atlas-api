# 015 - Perfil do país: como vive o povo
Status: done (no ar) (revisado em 2026-11-13) | Contrato: v1.2 | Web: atlas-web/specs/015-country-profile.md | Executor: Sonnet

## Dados
| Grupo | Indicador | Fonte (licença a citar) |
|---|---|---|
| Vida | expectativa de vida SP.DYN.LE00.IN, mortalidade infantil SP.DYN.IMRT.IN, fecundidade SP.DYN.TFRT.IN | World Bank WDI, CC BY 4.0 |
| Vida | IDH | UNDP HDR (hdr.undp.org, dados CSV; ler licença) |
| Vida | idade mediana | UN WPP (population.un.org; ler licença) ou OWID |
| Sociedade | urbanização SP.URB.TOTL.IN.ZS, alfabetização SE.ADT.LITR.ZS, internet IT.NET.USER.ZS, homicídios VC.IHR.PSRC.P5 | WDI |
| Sociedade | anos de estudo | UNDP HDR |
| Sociedade | religião e etnia (composição) | Wikidata P140/P172 com qualificador de proporção (P1107) quando houver; senão omitir |
| Renda | PIB pc PPP, Gini SI.POV.GINI, pobreza SI.POV.DDAY, desemprego | WDI |
| Ambiente | CO2 pc EN.GHG.CO2.PC.CE.AR5, renovável EG.FEC.RNEW.ZS, floresta AG.LND.FRST.ZS | WDI |
Ranking e régua: calculados no import sobre o último ano disponível por país (só países com dado; `rank_of` = quantos tinham).
Média regional: média simples dos países da mesma `region`.

## Contract delta (v1.2)
```
GET /v1/countries/{iso2}/profile -> { groups: [{ id: "life"|"society"|"income"|"environment",
    indicators: [{ id, label, unit, value, year, source_id, rank: int|null, rank_of: int|null,
                   world: { min, median, max }|null, region_avg: number|null }] }],
  composition: { religion: [{ label, share }]|null, ethnicity: [{ label, share }]|null, year: int|null, source_id: string|null },
  sources: Source[] }
```

## Design
- Mesma tabela `indicators` da spec 009; estatísticas mundiais/regionais pré-calculadas em `indicator_stats(id, year, min, median, max)`.
- Composição: no ETL do Wikidata; só entra se a soma das proporções ficar entre 80% e 105% (senão é dado incompleto: null).

## Tarefas
- [x] ler licenças UNDP/UN WPP; citar
- [x] indicadores no ETL; `indicator_stats`; composição Wikidata; endpoint; testes

## Licenças lidas (2026-11-12)
- **World Bank WDI**: CC BY 4.0 (https://datacatalog.worldbank.org/public-licenses#cc-by), atribuição "The World Bank: <dataset>: <fonte>".
  A API clássica (api.worldbank.org) respondeu 502/timeout o dia todo; o ETL lê o MESMO dataset (WB_WDI) da API Data360 do Banco Mundial
  (https://data360api.worldbank.org/data360/data). ISO3 → ISO2 via Wikidata P298.
- **UNDP HDR** (https://hdr.undp.org/terms-use): "All materials provided on this website are copyrighted under the Creative Commons
  Attribution 3.0 IGO license" ... "Share ... Adapt ... for any purpose, even commercially" ... "You must give appropriate credit, provide a
  link to the license, and indicate where changes were made." Há download direto utilizável (CSV "All composite indices and components time
  series (1990-2023)"), então IDH (`HDR.HDI`) e anos médios de estudo (`HDR.MYS`) ENTRAM. Não mudamos valores.
- **Idade mediana (UN WPP / OWID): não feita** (YAGNI nesta fase; o WPP é um download grande e o perfil já tem 16 indicadores). Fica null/ausente.

## O que foi feito
- `python -m etl worldbank` (23 indicadores desde 1990) + `python -m etl undp` → tabela `indicators(iso2, id, year, value, source_id)`
  (migração 0009, a mesma da spec 009), `indicator_defs` (rótulo/unidade pt-BR), `indicator_stats` (min/mediana/máx mundial sobre o último
  valor de cada país, `n` = `rank_of`) e `indicator_latest` (último valor, `rank` 1 = maior, média simples da `region`). Tudo no import.
- Composição: Wikidata P140 (religião) / P172 (etnia) com qualificador P1107; por país, o conjunto datado mais recente cuja soma fica entre
  80% e 105% (sem data = mais antigo); fora disso null.
- `GET /v1/countries/{iso2}/profile` (texto exato em CR-003). Indicador sem dado para o país sai do grupo.

## Cobertura (banco local, 197 países, 2026-11-12) — países com valor / ano mais recente
| id | países | | id | países |
|---|---|---|---|---|
| SP.DYN.LE00.IN | 195 (2024) | | SI.POV.GINI | 171 (1992-2025) |
| SP.DYN.IMRT.IN | 194 (2024) | | SI.POV.DDAY | 171 (1992-2025) |
| SP.DYN.TFRT.IN | 195 (2024) | | SL.UEM.TOTL.ZS | 179 (2021-2025) |
| HDR.HDI | 192 (2023) | | EN.GHG.CO2.PC.CE.AR5 | 186 (2024) |
| SP.URB.TOTL.IN.ZS | 195 (2025) | | EG.FEC.RNEW.ZS | 192 (2021-2022) |
| SE.ADT.LITR.ZS | 156 (1990-2024; países ricos não medem) | | AG.LND.FRST.ZS | 194 (2023-2024) |
| IT.NET.USER.ZS | 195 (2004-2025) | | NY.GDP.PCAP.PP.CD | 191 (2011-2025) |
| VC.IHR.PSRC.P5 | 177 (1994-2023) | | HDR.MYS | 192 (2023) |
Sem quase nada: TW e VA (o Banco Mundial não os lista), KP, MC, XK parciais. Composição: religião **8/197**, etnia **40/197** (a Wikidata
raramente tem P1107 que fecha 80-105%): o front deve tratar `null` como normal.

## Tarefas
- [x] ler licenças UNDP/UN WPP; citar (WPP não usado)
- [x] indicadores no ETL; `indicator_stats`; composição Wikidata; endpoint; testes (`tests/test_v12_api.py`, `tests/test_v12_build.py`)
