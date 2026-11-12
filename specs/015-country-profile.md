# 015 - Perfil do país: como vive o povo
Status: approved | Contrato: v1.2 | Web: atlas-web/specs/015-country-profile.md | Executor: Sonnet

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
- [ ] ler licenças UNDP/UN WPP; citar
- [ ] indicadores no ETL; `indicator_stats`; composição Wikidata; endpoint; testes
