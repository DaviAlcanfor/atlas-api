# 006 — Governantes e espectro político
Status: in progress (v1.1 feito, aguardando contrato; v1.2 não iniciado) | Contrato: v1.1 (governantes), v1.2 (espectro) | Web: atlas-web/specs/006-leaders-spectrum.md

## Dados
**Governantes** — Wikidata (CC0):
- país → cargos: P1906 (cargo do chefe de Estado), P1313 (cargo do chefe de governo);
- ocupantes: pessoas com `p:P39` = cargo, qualificadores P580 (início) / P582 (fim);
- pessoa: P102 (partido; escolher o válido na data do mandato quando houver qualificadores), P18 (foto no Commons:
  licença **por arquivo**, buscar autor/licença na API `imageinfo` do Commons; sem licença clara = sem foto), sitelink pt, senão en.
- Mesmo cargo para Estado e governo (presidencialismo) → `role` duplicado não; o web junta.

**Espectro** (v1.2) — candidatas, licenças a ler e citar antes de codar:
| Fonte | Cobertura | Escala | Licença (a confirmar) |
|---|---|---|---|
| V-Party (V-Dem) | ~1.900 partidos, ~170 países, 1970+ | especialistas, esquerda–direita econômica | CC BY-SA 4.0 |
| ParlGov | partidos e gabinetes UE/OCDE | 0–10 | CC BY-SA |
| Party Facts | crosswalk entre as bases acima e o Wikidata | — | a confirmar |
`value` = `raw` normalizado para −1..1 pela escala declarada da fonte; nenhuma outra conta.

## Contract delta
```
Leader { person_id, name, role: "head_of_state"|"head_of_government", office, start: string|null, end: string|null,
         party: { id, name }|null, image: { url, credit, license }|null, wikipedia_url: string|null }
GET /v1/countries/{iso2}/leaders?role= -> { items: Leader[] }                          (v1.1)
Leader += position: { scale: "left_right_economic", value, raw, raw_scale, year, source_id } | null   (v1.2)
```

## Design
- `python -m etl wikidata-leaders`: um SPARQL por país (196 × pausa de 1 s), cache em `etl_cache/wikidata/leaders/`.
- Tabelas `leaders` (person_id, polity_id, role, office, start, end, party_id, image...), `parties`.
- Escrita via `import-facts` (regra: só o CLI escreve).
- v1.2: `party_positions` (party_id, source, year, raw, value) + crosswalk Party Facts.

## Tarefas
- [x] SPARQL de governantes testado em BR, DE, JP, GB, US; contagens abaixo
- [x] tabela `leaders` (migração 0005), import, endpoint, testes (v1.1). Sem tabela `parties` (só precisa na v1.2)
- [ ] ler licenças V-Party/ParlGov/Party Facts e citar; crosswalk; posições (v1.2)

## Decisões abertas
1. Espectro: V-Party + ParlGov (recomendado)?
2. Coalizão: um marcador por partido (recomendado, sem cálculo) ou média ponderada por cadeiras?

## Resultado do SPARQL (2026-11-11)
Duas etapas: (1) uma query com P1906/P1313 de todos os países; (2) por país, ocupantes desses cargos via `VALUES`.
País -> cargo -> ocupantes numa query só dava 504 (timeout). `P31 Q5` (humano) vem de `BIND(EXISTS ...)` e é filtrado
em Python (como padrão triplo também dava timeout); sem isso entram itens como "Eleição presidencial no Brasil em 1998".

| País | Mandatos | Chefe de Estado | Chefe de governo | Com foto (licença+autor) | Com partido |
|---|---|---|---|---|---|
| BR | 42 | 42 | 0 (mesmo cargo) | 42 | 34 |
| DE | 23 | 12 | 11 | 22 | 19 |
| JP | 218 | 110 (imperadores) | 108 | 207 | 68 |
| GB | 85 | 5 (P39 só nos monarcas recentes) | 80 | 79 | 76 |
| US | 47 | 47 | 0 (mesmo cargo) | 47 | 42 |

- Foto: só com `LicenseShortName` E `Artist` no `extmetadata` do Commons e só se a pessoa tem UM P18; thumbnail 320px.
- Partido: o P102 válido no início do mandato; mais de um candidato = null (ex.: Bolsonaro, dois partidos sem datas).
- Datas a.C. ou com menos de 4 dígitos (imperadores lendários do JP) ficam `start: null`: o formato é "YYYY-MM-DD".
- Os dados são o que o Wikidata diz hoje (ex.: GB mostra Keir Starmer até 2026-07-20 e Andy Burnham depois).

## Cobertura completa (196 países, 2026-11-11)
10.645 mandatos; 196/196 países com pelo menos um; 195 com um mandato em aberto (`end: null` e `start` conhecido);
6.574 com foto (licença + autor), 4.936 com partido. A rodada completa levou ~1 h (o endpoint estava lento: 504
e conexões cortadas, tratados com novas tentativas de 15/30/45 s).
