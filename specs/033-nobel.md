# 033 — Prêmios Nobel por país
Status: in progress (aprovada pelo dono em 2026-11-17: "planeja como fazer o resto e dale", onda 3 do `atlas-web/specs/PLAN.md`) |
Contrato: CR-014 | Web: atlas-web/specs/033-nobel.md (espelho a criar; notas em "Web" abaixo) | Backlog: B7

## Por quê
"Quantos Nobel o país tem, de quem e por quê." Seção nova do painel.

## Dados
- **Fonte**: Nobel Prize API v2.1, `GET https://api.nobelprize.org/2.1/laureates?offset=&limit=1000` (2 chamadas: 1.028
  laureados, 1.036 prêmios em 2026-11-17). Cada resposta aponta para os termos em `meta.terms`/`meta.license`.
- **Termos lidos em 2026-11-17** (https://www.nobelprize.org/about/terms-of-use-for-api-nobelprize-org-and-data-nobelprize-org/):
  - "The Services are free to use according to the Creative Commons Zero (CC0) license."
  - "Applications that use the Services should not deliberately alter or censor the data, or deliberately mislead the end users."
  - "Applications shall be constructed in a manner which minimizes the capacity burden of the API. Consider using a local
    cache instead of performing many API calls." (ETL manual, 2 chamadas; o site nunca chama a API do Nobel.)
  - "Applications and other products and services may not use Nobel Prize Outreach's name, logos, or other trademarks in their
    titles or logos, or in any way that implies endorsement ... However, you are encouraged to cite the Services as the data
    source for your application." (Sem logo do Nobel; citar a fonte.)
  - Fotos dos laureados NÃO entram (não fazem parte da API; direitos à parte).
- **País**: `countryNow` (fronteiras de hoje) do local de nascimento (pessoa) ou de fundação (organização), e de cada
  afiliação na época do prêmio; casado com os nossos países pelo Q-id do Wikidata (`sameAs`) = `polities.wikidata_qid`.
  Exceções explícitas: Q55 Países Baixos -> NL (o nosso NL é o Reino), Q26 Irlanda do Norte -> GB. Ilhas Faroé e Guadalupe
  ficam null (territórios, não são países aqui). Sem país na API (ex.: União Europeia, PMA): null.
- **Cobertura** (2026-11-17): país de origem 1.027/1.036 prêmios; afiliações com país 853/856 (sem país: LIGO/VIRGO
  Collaboration); 83 países com pelo menos um prêmio. EUA 309 nascidos, Reino Unido 113, Alemanha 86, França 66; Brasil: 1
  (Peter Medawar, nascido no Rio de Janeiro, Medicina 1960, afiliado ao University College de Londres).
- **Motivação**: o texto oficial em inglês da API, sem tradução (nem por IA). Nomes em inglês (`knownName.en`).

## Contract delta (CR-014)
```
NobelAffiliation { name: string, city: string|null, iso2: string|null /* today's borders; null = not a /v1/countries country */ }
NobelPrize { laureate_id: string, name: string, kind: "person"|"organization", year: int,
             category: "physics"|"chemistry"|"medicine"|"literature"|"peace"|"economics",
             motivation: string|null /* official English text, verbatim */, portion: string|null /* "1", "1/2", "1/3", "1/4" */,
             born_here: boolean /* born (organization: founded) in this country */, affiliated_here: boolean,
             affiliations: NobelAffiliation[], wikipedia_url: string|null, url: string /* nobelprize.org laureate page */ }
CountryNobel { born: int, affiliated: int /* prize counts */, items: NobelPrize[] /* newest first */, sources: Source[] }
GET /v1/countries/{iso2}/nobel -> CountryNobel     Unknown iso2 -> 404; no laureate -> items [], born 0, affiliated 0, sources [].
```
Fonte (`sources[0]`): id `nobelprize`, "Nobel Prize API v2.1 (Nobel Prize Outreach)", licença "CC0 1.0".

## Design
- `python -m etl nobel` -> `data_out/nobel.json`; `python -m atlas_api.cli import-nobel` grava só `nobel_prizes` e a linha
  de fonte, numa transação, e entra no `data_version` (parte `nobel`).
- Migração **0021** (`nobel_prizes`, aditiva), depois da 0020 (spec 032). Mergear 032 antes.
- Atualização: manual (o prêmio sai uma vez por ano, em outubro): rodar o ETL + `import-nobel`.

## Web (para o espelho em atlas-web)
- Seção "Prêmios Nobel" no painel do país, só se `items` não vazio: resumo "N laureados nascidos aqui · M prêmios com
  afiliação aqui"; lista por ano (mais novo primeiro) com nome, categoria (rótulo pt-BR no cliente: Física, Química,
  Medicina, Literatura, Paz, Economia), "nasceu aqui" / "afiliação aqui", motivação em inglês entre aspas (sem traduzir,
  marcada `lang="en"`), link para `url`. Filtro por categoria opcional.
- Crédito: "Dados: Nobel Prize API (Nobel Prize Outreach), CC0". Sem logo nem marca do Nobel no título da seção além do nome.

## Tarefas
- [x] termos lidos e citados
- [x] ETL `nobel`, migração 0021, `import-nobel`, `GET /v1/countries/{iso2}/nobel`, testes com resposta gravada
- [x] CR-014, `openapi.generated.json`, `import-prod-033.ps1` ensaiado
- [ ] web (outra sessão)

## Decisões abertas
- Mostrar também o país de nascimento "da época" (`birth.place.country`, ex.: "Prussia")? Hoje só fronteiras atuais.
