# 003 — Pistas de GeoGuessr
Status: done (aguardando deploy (contrato v1.1 aplicado)) | Contrato: v1.1 | Web: atlas-web/specs/003-geoguessr.md

## Por quê
O web mostra um bloco "Pistas" (lado de dirigir, DDI, domínio, placa, alfabetos). O link do Plonk It é só do web.

## Dados
Wikidata (CC0), mesmas queries de país (`STATE`) do `etl/wikidata/pipeline.py`:
P1622 lado de dirigir (Q11920728 = esquerda; o Q13196750 citado antes não existe; Q14565199 = direita), P474 código telefônico, P78 domínio de topo,
P395 código de placa, P282 sistema de escrita dos idiomas oficiais (P37 → P282).
Vários valores para um campo escalar (ex.: dois domínios) → escolher o de rank preferido; empate = null + log.

## Contract delta
`CountryDetail += clues: { driving_side: "left"|"right"|null, calling_code: string|null, tld: string|null, plate_code: string|null, scripts: string[] } | null`
(`null` quando nenhum campo tem dado.)

## Design
- 5 entradas novas no dicionário de queries; colunas novas em `countries` (migração 0003); `facts.py` copia; schema + query.

## Tarefas
- [x] queries + build; migração 0004; `import-facts`; schema; testes (linhas inline, sem rede)

## Resultado (2026-11-11, cache do Wikidata)
Cobertura: driving_side 196/196, calling_code 195/196, tld 194/196, plate_code 172/196, scripts 178/196.
Nulos por empate (logados): DO (3 DDIs +1809/+1829/+1849), RU (.ru e .su), TD (placas TCH e TD).
- TLD: em empate, um único ccTLD ASCII de 2 letras vence IDN/marcas (`.jp` contra o IDN japonês, `.ch` contra `.swiss`).
- `scripts`: P282 traz alfabetos por língua ("alfabeto francês", "French Braille"). Subimos por P279/P282 até um
  sistema com código ISO 15924 (P506), excluindo Braille, Deseret, Shavian e códigos compostos (Jpan, Hrkt, Kore).
  Sem caminho no Wikidata = `[]` (ex.: FR, SE, CZ); o kanji do Japão também não aparece (o Wikidata liga kanji a Hani
  só por "baseado em", que não seguimos para não puxar ancestrais históricos).
