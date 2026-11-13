# 026 - Organizações, DDD dos estados, resumo da história melhor
Status: in progress (aprovada pelo dono em 2026-11-13) | Contrato: v1.3 (CR-004 addendum 4) | Web: atlas-web/specs/026-polish-round-3.md

## Pedidos
1. "As organizações do Brasil não estão todas: não tem Mercosul e BRICS, só a ONU."
2. "Dá pra pegar também o DDD dos estados de todos os países?"
3. "O resumo do Brasil ainda está um pouco ruim."

## Data
- **Organizações**: o P463 do Wikidata só é completo para a ONU (medido em 2026-11: OTAN 29/32, UE 26/27, OCDE 35/38). Lista
  curada `content/organizations.yaml`, uma fonte por organização (site oficial ou Wikipédia), com data de consulta. Membro suspenso
  continua membro (ex.: União Africana); Venezuela no Mercosul está suspensa desde 2016 e fica fora (nota no arquivo). O ETL
  `wikidata` junta a lista curada às da ONU. Rascunho do agente: precisa de revisão humana como o `glossary.yaml`.
- **DDD**: Wikidata P473 ("local dialing code", CC0) nos estados tem cobertura baixa (2026-11-13: BR 1/27, US 6/51, JP 0/47,
  IT 95/110, RU 32/85). Brasil: tabela curada `content/area_codes.yaml` a partir do Plano de numeração da Anatel (códigos
  nacionais por área; informação pública de órgão federal, sem restrição de reuso para fatos). O curado vence o Wikidata.
- **História**: mesma fonte (pt.wikipedia, CC BY-SA 4.0). O condensado continua mecânico: período = 1º parágrafo da seção + 1º
  trecho (até 2 frases) de cada subseção, prefixado pelo título dela.

## Contract delta (CR-004 addendum 4)
```
Subdivision { ...; area_codes: string[] /* telephone area codes (DDD); [] = no data */ }
```
`SubdivisionList.sources` passa a incluir a Anatel quando algum item usa a tabela curada.

## Tarefas
- [ ] `content/organizations.yaml` + merge no ETL + verbetes no glossário
- [ ] migração 0015 (`subdivisions.area_codes`), ETL (P473 + curado), import, schema, testes
- [ ] condensação dos períodos com subseções + testes
- [ ] CR-004 addendum 4; regenerar `openapi.generated.json`
