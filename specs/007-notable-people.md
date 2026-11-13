# 007 — Pessoas importantes
Status: done (no ar) (revisado em 2026-11-13) | Contrato: v1.1 | Web: atlas-web/specs/007-notable-people.md

## Dados
| Fonte | O que é | Licença (a confirmar) |
|---|---|---|
| Pantheon (pantheon.world) | ~88 mil biografias, "Historical Popularity Index", país de nascimento, ocupação categorizada | CC BY-SA 4.0 |
| Wikidata | foto (P18) e sitelink, pelo Q-id que o Pantheon já traz | CC0 (foto: licença por arquivo) |
Recomendado: ranking e ocupação do Pantheon; Wikidata só para foto e link.
Viés conhecido: super-representa homens, Europa e figuras antigas. Vai em `method`.
País = país moderno do local de nascimento (decisão da fonte); documentar.

## Contract delta
```
Person { id, name, occupation, domain, birth_year: int|null, death_year: int|null, image: { url, credit, license }|null,
         wikipedia_url: string|null, rank: int }
GET /v1/countries/{iso2}/people?domain=&limit= -> { items: Person[], method: string, source: Source }
```

## Design
- `python -m etl pantheon`: baixa o dataset (arquivo, não scraping), filtra top 50 por país, grava `data_out/pantheon.json`.
- Tabela `people`; `import-facts` grava. `domain` = os 8 domínios do próprio Pantheon (ver decisões).

## Tarefas
- [x] ler licença e formato do dataset; citar aqui (abaixo)
- [x] ETL (`python -m etl pantheon`), tabela `people` (migração 0006), import, endpoint, testes

## Licença e formato (lidos em 2026-11-11)
- https://pantheon.world/data/permissions: "Pantheon by Datawheel is licensed under a Creative Commons
  Attribution-ShareAlike 4.0 International License." e "If you use the Pantheon dataset, please cite:" Yu, A. Z., et al.
  (2016) Pantheon 1.0, a manually verified dataset of globally famous biographies. Scientific Data 3:150075.
- https://pantheon.world/data/datasets: download direto, sem login. Usamos
  `https://storage.googleapis.com/pantheon-public-data/person_2025_update.csv.bz2` (12 MB, CSV bzip2, 126.582 pessoas;
  colunas `wd_id, name, occupation, bplace_country, birthyear, deathyear, hpi`, ...).
- ShareAlike: o que servimos dele fica CC BY-SA 4.0 com atribuição; `source.license` carrega licença + citação.
- Domínio da ocupação: taxonomia do próprio Pantheon em `https://api.pantheon.world/occupation` (102 ocupações, 8 domínios).
- Anos: o Pantheon escreve 100 a.C. como -100 (César: -100, "0100-07-01 BC"), igual à nossa convenção; ano 0 vira null.
- País: `bplace_country` (nome em inglês) -> ISO2 pelos rótulos/aliases em inglês do Wikidata + `NAME_FIXES`.

## Decisões abertas
1. `occupation` e `name` ficam em inglês (como o Pantheon publica). Traduzir as 102 ocupações para pt-BR?
2. Domínios: usamos os 8 do Pantheon (arts, business_law, exploration, humanities, institutions, public_figure,
   science_technology, sports). Reagrupar em 5 seria escolha nossa; manter 8?

## Resultado (2026-11-11)
Top 50 por país: 7.699 pessoas importadas, 196/196 países (VA tem só 4). 6.360/7.749 com foto (licença + autor),
7.734 com link da Wikipédia, 4 sem domínio e 62 linhas do dataset sem ocupação (`occupation: null`).
Nomes do Pantheon fora dos 196 (territórios: Porto Rico, Hong Kong, Groenlândia...) ficam de fora e são listados pelo ETL.
Achado: `DK` (Dinamarca) aparece no Pantheon, mas NÃO está nos 196 países do seed (o Wikidata usa "Reino da Dinamarca"
para o Estado soberano). Lacuna anterior a esta spec; o import ignora DK até o seed ser corrigido.
