# 032 — Organizações internacionais com datas de entrada e saída
Status: in progress (aprovada pelo dono em 2026-11-17: "planeja como fazer o resto e dale", onda 3 do `atlas-web/specs/PLAN.md`) |
Contrato: CR-013 | Web: atlas-web/specs/032-organizations.md (espelho a criar; notas em "Web" abaixo) | Backlog: B4 (amplia 026)

## Por quê
O painel já mostra a lista "Organizações" (`CountryDetail.memberships`, rótulos do glossário; spec 026), mas só os membros
atuais, sem datas, e sem uma rota por organização (necessária para a camada no globo "quem faz parte da OTAN?"). B4 pede
membros **com datas de entrada e saída**.

## De onde vinha a lista de hoje (encontrado antes de codar)
`content/organizations.yaml` (spec 026: rótulo -> membros atuais, uma fonte por organização) era lido pelo ETL `wikidata`
(`add_curated_memberships`) e gravado em `country_facts.memberships` junto com a ONU do Wikidata P463; a API servia esse campo.
Esta spec **amplia o mesmo arquivo** (agora com datas) e o leva ao banco pelo `import-content`; não há lista duplicada.

## Dados
- **Fonte por organização**: artigo-lista da Wikipédia em inglês, citado por **permalink da revisão** (`oldid`), lido em
  2026-11-17. Licença da Wikipédia: "Text is available under the Creative Commons Attribution-ShareAlike 4.0 License"
  (rodapé de toda página). Usamos só fatos (país, data), nenhum texto copiado; a fonte fica em `sources` de cada organização
  e o cliente a mostra.
  | id | Organização | Revisão citada | Membros atuais / períodos |
  |---|---|---|---|
  | onu | ONU | Member states of the United Nations, oldid 1385797650 | 193 / 193 |
  | uniao-europeia | União Europeia | Member state of the European Union, oldid 1386146667 | 27 / 28 (Reino Unido 1973–2020) |
  | otan | OTAN | Member states of NATO, oldid 1383947570 | 32 / 32 |
  | ocde | OCDE | OECD, oldid 1386155426 | 38 / 38 |
  | opep | OPEP | OPEC, oldid 1384638255 | 11 / 19 (Catar, Equador x2, Indonésia x2, Gabão 1975–1995, Angola, Emirados) |
  | asean | ASEAN | Member states of ASEAN, oldid 1368489261 | 11 / 11 |
  | uniao-africana | União Africana | Member states of the African Union, oldid 1384120008 | 54 / 55 (Marrocos 1963–1984 na OUA) |
  | brics | BRICS | Member states of BRICS, oldid 1381460796 | 10 / 10 |
  | g7 | G7 | G7, oldid 1386063718 | 7 / 7 |
  | g20 | G20 | G20, oldid 1386105485 | 19 / 19 |
  | mercosul | Mercosul | Mercosur, oldid 1384013871 | 6 / 6 |
  | cplp | CPLP | Member states of the Community of Portuguese Language Countries, oldid 1359374312 | 9 / 9 |
- **Datas**: string ISO 8601 com a precisão da fonte (`"1960"`, `"1975-11"`, `"1949-08-24"`). OPEP, G7 e CPLP (entradas
  tardias) só dão o ano. União Africana: data de adesão à OUA (antecessora, 1963–2002), como na fonte. UE: fundadores em
  25/03/1957 (assinatura do Tratado de Roma), como na fonte. OCDE: data do depósito da ratificação (última data da linha).
- **Suspensos** continuam membros (`suspended: true`): União Africana (Burkina Faso, Guiné-Bissau, Madagascar, Mali, Níger,
  Sudão, conforme a legenda da revisão citada), Mercosul (Venezuela, desde 01/12/2016), CPLP (Guiné-Bissau, 2025).
  **Mudança vs. 026**: a Venezuela estava fora do Mercosul; agora aparece como membro suspenso (é o status jurídico).
- **Mudanças de fato encontradas** (a lista de 2026-11-13 estava desatualizada): os **Emirados Árabes Unidos saíram da OPEP
  em 01/05/2026** (OPEC, oldid 1384638255: "The UAE ... announced it was withdrawing from OPEC and OPEC+ in effective May 1,
  2026"). Angola: a tabela de ex-membros diz 2007–2023.
- **Inconsistências dentro da mesma fonte** (ficou a tabela, nota no YAML): Gabão na OPEP (tabela 1975–1995, texto
  1975–1994); Indonésia na OPEP (tabela jan–nov 2016, texto 2014–2016).
- **Fora**: Arábia Saudita no BRICS (status disputado na própria fonte); a Rússia no G8 (1997–2014, outro grupo); membros sem
  ISO 3166 (República Árabe Saaraui Democrática na UA; UE e UA no G20).
- **Conferência com o Wikidata** (P463 + qualificadores P580/P582 dos itens com P297, consulta de 2026-11-17). Membros atuais
  curados x Wikidata; "sem data" = membros presentes nos dois sem P580:
  | Org (QID) | Curado / Wikidata | Só no curado | Só no Wikidata | Sem data no WD | Ano de entrada diferente |
  |---|---|---|---|---|---|
  | ONU (Q1065) | 193 / 192 | DK | - | 0 | 16: o WD data o Estado sucessor (RU 1991, UA 1991, BY 1991, CN 1971, EG 1971, YE 1990, TZ 1964, MY 1963, AZ 1991...), ID 1966 (volta), PH 1946, ZA 1961, BI, BJ, CF, GY |
  | UE (Q458) | 27 / 26 | NL | - | 0 | DE 1958-01-01 (vigência do Tratado de Roma) vs 1957-03-25 (assinatura) |
  | OTAN (Q7184) | 32 / 30 | DK, NL | - | 0 | - |
  | OCDE (Q41550) | 38 / 36 | DK, NL | - | 21 | - |
  | OPEP (Q7795) | 11 / 13 | - | AE, AO (saíram: 2026 e 2023) | 0 | - |
  | ASEAN (Q7768) | 11 / 12 | - | AU (erro do WD: a Austrália é parceira) | 0 | - |
  | UA (Q7159) | 54 / 54 | - | - | 44 | EG 2002 (data da UA), TZ 1964 |
  | BRICS (Q243630) | 10 / 10 | - | - | 5 | - |
  | G7 (Q1764511) | 7 / 7 | - | - | 1 | todos 1977-01-01 no WD vs 1975/1976 na fonte |
  | G20 (Q19771) | 19 / 19 | - | - | 13 | - |
  | Mercosul (Q4264) | 6 / 7 | - | MX (erro do WD: o México não é membro) | 6 | - |
  | CPLP (Q182500) | 9 / 9 | - | - | 8 | - |
  DK e NL faltam no WD porque lá a filiação está no item do Reino (Q756617, Q29999), não no país com o código ISO. Conclusão:
  o Wikidata confirma os conjuntos (salvo os erros acima), mas as datas são incompletas ou de outro critério; fica a lista curada.

## Contract delta (CR-013)
```
OrganizationMember { iso2: string, joined: string /* ISO 8601, precision of the source: "YYYY" | "YYYY-MM" | "YYYY-MM-DD" */,
                     left: string|null /* same format; null = still a member */, suspended: boolean, note: string|null }
Organization       { id: string /* = GlossaryTerm.id, kind "membership" */, label: string, short: string, icon: string|null,
                     wikidata_qid: string|null, note: string|null,
                     members: OrganizationMember[] /* every period, current and former, by joined then iso2 */,
                     sources: Source[] }
CountryMembership  { id: string, label: string, joined: string, left: string|null, suspended: boolean, note: string|null }
GET /v1/organizations                 -> { items: Organization[] }          by label
GET /v1/countries/{iso2}/organizations -> { items: CountryMembership[], sources: Source[] }
                                         current first (by label), then former (latest `left` first); unknown iso2 -> 404
```
`CountryDetail.memberships` (sem mudança de tipo): para as 12 organizações curadas passa a vir da lista curada (só membros
atuais, suspensos incluídos), em vez do `wikidata.json`.

## Design
- Migração **0020** (`organizations`, `organization_members`; aditiva). 0019 é da spec 024 fase 2 (já no `main`).
- `import-content` valida e reconstrói as duas tabelas: organização = termo do glossário de kind `membership`; fonte com
  título, url, licença e data; ISO2 conhecido (entre aspas); datas no formato; `left` não antes de `joined`; no máximo um
  período aberto por país.
- O ETL `wikidata` não mescla mais a lista curada (`add_curated_memberships` removido); a API aplica a curada por cima do
  P463 (`queries._curated`), também nos exemplos do glossário.
- Cache: ETag por `data_version` como o resto (muda quando o `import-content` roda).

## Web (para o espelho em atlas-web)
- Seção "Organizações" do painel: trocar os chips de `CountryDetail.memberships` por `GET /v1/countries/{iso2}/organizations`:
  chip com o rótulo + "desde 1945" (ano de `joined`); suspenso = chip apagado com "suspenso"; ex-membros numa linha
  "Já fez parte: OPEP (1967–2026)". O verbete do glossário continua no clique.
- Camada no globo: seletor de organização (`GET /v1/organizations`, uma chamada, ~430 períodos) pinta os membros atuais
  (`left == null`); opcional, um controle de ano pinta quem era membro naquele ano (comparar só os 4 primeiros dígitos).
- Créditos: mostrar `sources` (Wikipédia, CC BY-SA 4.0, link da revisão).

## Tarefas
- [x] `content/organizations.yaml` com datas, fonte por revisão, notas
- [x] migração 0020, modelos, import + validação, `GET /v1/organizations`, `GET /v1/countries/{iso2}/organizations`
- [x] `CountryDetail.memberships` e exemplos do glossário a partir da lista curada; ETL sem a mescla
- [x] testes; CR-013; `openapi.generated.json`
- [x] `import-prod-032.ps1` ensaiado numa cópia do banco local
- [ ] revisão humana do YAML (rascunho do agente)
- [ ] web (outra sessão)

## Decisões abertas
- Venezuela no Mercosul como "suspensa" (antes ficava fora). Reverter = tirar a linha do YAML.
- Mais organizações (Commonwealth, Liga Árabe, OEA, CEI...) = só YAML + verbete no glossário.
