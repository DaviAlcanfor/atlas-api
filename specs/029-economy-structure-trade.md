# 029 - Do que vive a economia: setores, exportações, parceiros (e relações diplomáticas)
Status: in progress (aprovada pelo dono em 2026-11-15: "aprovado tudo"; fase 2 da API em PR, 2026-11-16) | Contrato: fase 1 = CR-009 (grupo novo no perfil); fase 2 propõe rota nova |
Web: atlas-web/specs/029-economy-structure-trade.md | Backlog de origem: B1, B13, B14 do PLAN

## Por quê
Pedido do dono: saber o que cada país exporta, se a economia se apoia em tecnologia, agricultura, petróleo etc., e quais
relações diplomáticas ele tem. Hoje o painel mostra PIB, inflação, dívida... mas não **de onde vem** a renda.

## Fases
| Fase | O que entra | Fonte | Contrato |
|---|---|---|---|
| 1 | Estrutura da economia: peso de agro, indústria, manufatura e serviços no PIB; rendas de petróleo e de recursos naturais; composição das exportações de mercadorias (combustíveis, alimentos, matérias-primas agrícolas, minérios e metais, manufaturados) e alta tecnologia | Banco Mundial (WDI), já usado no projeto | 1a: **sem mudança** (o catálogo `GET /v1/indicators` já lista todo indicador com dado, então os 12 entram na camada Ranking). 1b: **CR-009**, grupo `economy` em `GET /v1/countries/{iso2}/profile` (o contrato fixa os grupos e os ids do `/economy`; corrigido em 2026-11-15) |
| 2 | O que o país exporta (produtos principais) e com quem negocia (principais destinos e origens) | BACI (CEPII) | Rota nova (proposta abaixo) |
| 3 | No globo: arcos do país selecionado até os principais parceiros (B14) | dados da fase 2 | sem mudança além da fase 2 |
| — | Relações diplomáticas | **em aberto** (ver Decisões) | — |

## Dados (lido em 2026-11-15)
### Banco Mundial (fase 1)
Licença CC BY 4.0 (já registrada no README da API para os outros indicadores). Indicadores candidatos:
`NV.AGR.TOTL.ZS`, `NV.IND.TOTL.ZS`, `NV.IND.MANF.ZS`, `NV.SRV.TOTL.ZS` (% do PIB); `NY.GDP.PETR.RT.ZS`, `NY.GDP.TOTL.RT.ZS`
(rendas, % do PIB); `TX.VAL.FUEL.ZS.UN`, `TX.VAL.FOOD.ZS.UN`, `TX.VAL.AGRI.ZS.UN`, `TX.VAL.MMTL.ZS.UN`, `TX.VAL.MANF.ZS.UN`
(% das exportações de mercadorias); `TX.VAL.TECH.MF.ZS` (alta tecnologia, % das exportações de manufaturados).
Cobertura medida em 2026-11-15 (ETL via Data360): 176 a 194 dos 197 países por indicador (faltam sobretudo KP, TW, VA e microestados;
alta tecnologia: 176). Uma só combinação de recortes por indicador (sem chaves repetidas). Exemplos: Arábia Saudita 79% das
exportações em combustíveis, Nigéria 86%, Coreia do Sul 88% em manufaturados (36% de alta tecnologia), Brasil 41% em alimentos.

### BACI, CEPII (fase 2)
- Página: https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37 — "Licence: Etalab 2.0"; "Last update: January 30,
  2026" (versão 202601); HS92 cobre 1995-2024; também HS96, HS02, HS07, HS12, HS17, HS22.
- Licença Etalab 2.0 (texto oficial, https://github.com/etalab/licence-ouverte, `open-licence.md`): "The 'Reuser' is free to reuse
  the 'Information' [...] To share, disseminate, redistribute, publish and transmit it", inclusive "for commercial or
  non-commercial purposes", **desde que** haja "an acknowledgement of the authorship of the 'Information': its source (at least,
  the name of the 'Grantor') and the date of the most recent update". Compatível com CC BY.
  Atribuição no Atlas: "CEPII, BACI (versão 202601, atualizada em 30/01/2026)" com link para a página acima.
- Citação acadêmica pedida pela página: Gaulier, G. e Zignago, S. (2010), "BACI: International Trade Database at the Product-Level.
  The 1994-2007 Version", CEPII Working Paper N°2010-23.
- Formato (https://www.cepii.fr/DATA_DOWNLOAD/baci/doc/DescriptionBACI.html): um CSV por ano, colunas `t` (ano), `k` (HS 6 dígitos;
  ler como texto), `i` exportador e `j` importador (código numérico de 3 dígitos), `v` valor em **milhares de USD correntes**,
  `q` toneladas; só fluxos positivos. O zip HS92 tem 2,4 GB (Content-Length); HS22 cobre só 2022-2024 e deve ser bem menor.
- Descartada: **UN Comtrade**. O acordo de licença (https://comtradeplus.un.org/en/license-agreement, seção 5) diz que "any copying,
  automated browsing or downloading, redistribution, publication, or commercial exploitation [...] is strictly prohibited without
  the prior written permission of the United Nations". O plano grátis também limita a 500 chamadas por dia.

#### Escolha feita na fase 2 (2026-11-16)
- **Revisão HS22**, versão 202601, ano **2024** (o mais recente; o zip HS22 tem 301 MB pelo Content-Length, contra 2,4 GB do HS92 e
  795 MB do HS17). Mesmo último ano em todas as revisões, e os produtos já vêm no SH 2022, que é o da tabela de nomes em português
  abaixo. O zip traz `BACI_HS22_Y2024_V202601.csv`, `country_codes_V202601.csv` e um Readme ("Values in thousand USD").
- Códigos de país: `country_codes_V202601.csv` (`country_code` -> `country_iso2`). Sem ISO2 nesse arquivo: "Other Asia, nes" (490,
  que é como o BACI publica Taiwan) e grupos regionais "nes": entram nos totais, nunca como parceiro; **TW fica sem dado (404)**.
  A Namíbia vem com ISO2 vazio (o "NA" foi lido como ausente), então usamos o ISO3 NAM do mesmo arquivo.
- Primeiro resultado (2024): 225 códigos com dado; Brasil exporta US$ 350 bi e importa US$ 276 bi; 1º produto óleos brutos de
  petróleo (13%), 1º destino China (27%). Arábia Saudita US$ 308 bi; Coreia do Sul US$ 721 bi, 1º produto circuitos integrados.
  Dos 197 países do Atlas, 192 ganham dado; sem BACI (-> 404): TW (acima), XK, LI, MC, VA (não estão no `country_codes` do BACI; os códigos 251 e 757 são os do Comtrade para França e Suíça, que nas Nações Unidas incluem Mônaco e Liechtenstein).
  Ensaio local de `import-prod-029.ps1` (cópia descartável do banco de dev, rodado 2 vezes): 0018 aplicada, 192 países.

### Nomes dos produtos em português (Decisão 2, lido em 2026-11-16)
- Tabela NCM do Siscomex (módulo Classif, JSON/XLSX): nenhuma licença ou termo de uso publicado encontrado.
- **Usada**: tabela auxiliar `NCM_SH.csv` do MDIC/Secex (https://balanca.mdic.gov.br/balanca/bd/tabelas/NCM_SH.csv), coluna
  `NO_SH4_POR` (1.274 posições, um nome por código). Página
  https://www.gov.br/mdic/pt-br/assuntos/comercio-exterior/estatisticas/base-de-dados-bruta: "Todo o conteúdo deste site está
  publicado sob a licença Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada" (CC BY-ND 3.0). A CC BY-ND 3.0 permite
  reproduzir e distribuir, inclusive dentro de uma coletânea ("Collection"), com atribuição; proíbe distribuir obra **adaptada**.
  Por isso os nomes são servidos **literalmente** (nem encurtados, nem reescritos; ex.: "Circuitos integrados e microconjuntos
  electrónicos", grafia do Mercosul), com a fonte `mdic-sh` em `sources`. Se o dono preferir nomes curtos, é preciso outra fonte.
- Toda posição de 4 dígitos exportada em 2024 tem nome nessa tabela; o ETL para com erro se faltar algum (nunca inventa).

### Relações diplomáticas
- Wikidata P530 ("relação diplomática", CC0) **não serve** como lista completa: medido em 2026-11-15, Brasil 75, EUA 182,
  Coreia do Norte 173, Canadá 87, Nigéria 29, Taiwan 14; só 6 das 75 do Brasil têm data de início. O Brasil tem relações com quase
  todos os países da ONU, então o dado é incompleto e desigual entre países.

## Contract delta (fase 2, proposta)
```
GET /v1/countries/{iso2}/trade -> {
  year: int, exports_usd: float, imports_usd: float,
  top_exports: [{ hs: string (4 dígitos), label: string (pt-BR), value_usd: float, share: float }],   // até 10
  top_destinations: [{ iso2: string, value_usd: float, share: float }],                               // até 10
  top_origins: [{ iso2: string, value_usd: float, share: float }],                                    // até 10
  sources: [Source]
}
```
404 para país sem dado no BACI. Agregação no ETL: soma por HS de 4 dígitos (6 dígitos é detalhado demais para o painel).

## Design (web, resumo; detalhes na spec do web)
- Painel do país: bloco "Do que vive a economia" (fase 1) com barras de setor e de composição das exportações, cada uma com ano e
  fonte. Nenhum rótulo inventado: a frase-resumo ("economia apoiada em petróleo") só aparece por regra explícita sobre os números
  (ex.: combustíveis > 50% das exportações), e a regra é mostrada no (i).
- Fase 2: "O que exporta" (top produtos) e "Com quem negocia" (top parceiros com bandeira).
- Fase 3: arcos no globo para os parceiros.

## Tarefas
- [x] Fase 1a: medir cobertura; 12 indicadores no ETL do Banco Mundial (entram no catálogo do ranking após `import-facts`)
- [ ] Fase 1b: CR-009 aplicada pelo dono; grupo `economy` no perfil + testes (web aceita o id ANTES do deploy da API)
- [ ] Fase 1 (web): bloco "Do que vive a economia"; verbetes de glossário dos termos novos
- [x] Fase 2: escolher revisão HS (HS22, 2024); ETL `python -m etl baci` -> `data_out/trade.json`; nomes pt-BR do MDIC (NCM_SH)
- [x] Fase 2 (API): CR-010 escrita; migração 0018 (`country_trade`); `import-trade`; `GET /v1/countries/{iso2}/trade` + testes
- [ ] Fase 2: o dono aplica a CR-010 no contrato dos 2 repos; roda `import-prod-029.ps1` (raiz do workspace) ANTES do merge
- [ ] Fase 2 (web)
- [ ] Fase 3: arcos no globo

## Decisões (tomadas em 2026-11-15, com a aprovação do dono às recomendações)
1. **Relações diplomáticas**: não mostrar até haver fonte completa e com licença lida. O P530 do Wikidata é incompleto (medido
   acima). Fontes a pesquisar depois: Lowy Institute Global Diplomacy Index, Pardee Center "Diplometrics", Correlates of War
   "Diplomatic Exchange" (só até 2005).
2. **Nomes dos produtos em português**: na fase 2, ler os termos da tabela NCM do governo brasileiro (os 6 primeiros dígitos seguem
   o SH) antes de usar; sem licença compatível, os nomes ficam em inglês com o código.
3. **Ano**: aceitar a defasagem do BACI (até 2024 na versão 202601), com o ano visível no bloco.
