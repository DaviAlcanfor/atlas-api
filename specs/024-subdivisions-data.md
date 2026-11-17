# 024 - Estados: dados e bandeira por subdivisão
Status: in progress (aprovada pelo dono em 2026-11-12: "vê o que tá pendente e já vai fazendo") | Contrato: v1.3 (CR-004) | Web: atlas-web/specs/024-subdivisions-data.md

## Dados (fase 1)
- Quais estados: os `wikidataid` dos polígonos admin-1 do web (Natural Earth), lidos de `ADMIN1_DIR` (padrão `../geo/public/data/admin1`):
  3.754 subdivisões em 240 países, a API responde exatamente pelos desenhos do globo.
- Wikidata (CC0): P300 código ISO 3166-2 (3.644), P36 capital (3.500), P2046 área normalizada em km² (3.643),
  P1082 população com ano (posição preferida, senão a data P585 mais recente; 3.377), P41 bandeira (1.740 com licença válida).
- Bandeiras: Commons, licença POR ARQUIVO (`extmetadata` `LicenseShortName` + `Artist`, mesma regra das fotos da 006); bandeira em
  domínio público/CC0 sem autor é aceita com crédito "Wikimedia Commons". Miniaturas espelhadas no Storage como as fotos.
- **Sem governador**: testado em 2026-11-12, o Wikidata está desatualizado (P6 do RJ = Witzel, afastado em 2021; a rota P1313 + P39
  traz governadores do século XIX sem data de fim). Governador errado é pior que nenhum. Fonte melhor fica para depois.
- IDH subnacional (Global Data Lab) e IBGE: fase 2, depois de ler os termos.

## Entregue (fase 1)
`python -m etl wikidata-subdivisions [ISO2...]` -> `data_out/subdivisions.json`; migração 0012 (`subdivisions`); `import-facts`;
`GET /v1/countries/{iso2}/subdivisions`; testes `tests/test_subdivisions.py`. Texto do contrato: CR-004.

## Dados (fase 2, lidos em 2026-11-16)
### IDH subnacional: Global Data Lab (SHDI v10.2)
- Site do GDL (https://globaldatalab.org/termsofuse/): "can be freely downloaded and used for noncommercial purposes ... provided
  that the Global Data Lab is mentioned as the source of the indicators and a link to the GDL website including the data and
  version of the download are clearly referenced"; "Commercial use is only possible after written permission". O CSV ali exige login.
- **Usamos a cópia arquivada pelos próprios autores no Radboud Data Repository** (https://doi.org/10.34973/qbpx-by38, v10.2,
  WebDAV público, sem login). Metadados DataCite: "Open Access" + "Creative Commons Zero v1.0 Universal". LICENSE.txt: "You can
  copy, modify, distribute and perform the work, even for commercial purposes, all without asking permission". ABOUT.txt pede a
  citação "Smits, J., Permanyer, I. (2026): Subnational Human Development Index (Global Data Lab). Version 1. Radboud University"
  (é o título da fonte `gdl-shdi`). O ETL confere o SHA256 do MANIFEST.txt.
- Junção região GDL -> nosso estado, nunca chutada (sem par = sem IDH): mesmo país; nome normalizado (sem acento/pontuação,
  sem "province/state/região...") igual a UM único nome do estado (rótulo pt, nome do polígono, rótulos Wikidata em 16 línguas
  latinas + apelidos em inglês), com o estado reivindicado por uma só região; e população GDL x Wikidata dentro de 1,5x
  (pega homônimos de outro nível: "Nord" do GDL = antiga região Nord-Pas-de-Calais, 4 M, x departamento Nord, 2,6 M).
- Resultado: **842 de 3.754 estados com IDH** (ano 2023). 1.771 regiões GDL nos nossos países; 185 recusadas pela população.
  Completos: BR 27/27, DE 16/16, ZA 9/9, AU 8/8; quase: US 50/51 (Washington é ambíguo com D.C.), CN 31/31, NG 34/37, MX 30/32,
  IN 31/35, ID 23/33. Zero onde o GDL agrupa províncias ou usa outro nível (AR, RU, GB, FR 4/100, ES 4/51, IT 2/110, JP 1/47,
  KE 5/8: províncias antigas x condados). Contagem por país em `data_out/shdi.json` -> `match`.

### Governador / chefe do estado
- Testado contra a lista da pt.wikipedia de governadores em exercício (editada em 2026-11-08): o Wikidata está velho.
  P6 no estado: 13/27 certos. P39 da pessoa no cargo P1313, início mais recente, sem fim (ou fim futuro), vivo: 17/27
  (perde a onda de renúncias de abril de 2026: AC, AM, DF, ES, GO, MG, PA, PB, RJ, RR). US: 47/51 iguais. IN: 30/31.
- **Fonte escolhida: as listas de titulares atuais da Wikipedia**, por país (BR: "Lista de governadores das unidades federativas
  do Brasil" na pt; US: "List of current United States governors"; IN: "List of current Indian chief ministers"). Texto CC BY-SA
  4.0 (Termos de Uso §7: atribuição = título + link); guardamos só fatos (nome, data de posse), citados pela revisão exata
  (permalink `oldid`). Linha -> estado pelo Wikidata id do artigo linkado (pageprops), nunca por nome; a pessoa vem com o id dela.
  Cobertura: BR 27/27, US 51/51 (50 estados + D.C., "Prefeito"), IN 31/35 (os 4 territórios sem ministro-chefe ficam sem).
- **Resto do mundo: sem governador.** O Wikidata, com a mesma regra (início, sem fim, vivo), teria titular para 1.023 de 3.602
  estados, mas errou 10/27 no Brasil e 4/51 nos EUA; governador errado é pior que nenhum. Fica desligado
  (`WIKIDATA_ELSEWHERE = False` em `etl/wikipedia/heads.py`); ligar é uma linha se o dono aceitar o risco.
  Outros países entram adicionando a lista da Wikipedia deles em `LISTS`.
- Governador muda entre importações: o campo traz `since` e a fonte; reimportar com `etl subdivision-heads --refresh`.

## Entregue (fase 2)
`python -m etl gdl-shdi` -> `data_out/shdi.json`; `python -m etl subdivision-heads` -> `data_out/heads.json`; migração 0019
(`subdivisions.hdi`, `hdi_year`, `head`); `import-facts` e o novo `import-subdivisions` (só a tabela subdivisions + fontes);
campos `hdi` e `head` no item de `GET /v1/countries/{iso2}/subdivisions`. Texto do contrato: CR-011. Produção: `import-prod-024b.ps1`.

## Tarefas (fase 2)
- [x] Ler termos do GDL e da Wikipedia; testar o Wikidata contra a lista atual
- [x] ETL `gdl-shdi` + `subdivision-heads`, migração 0019, endpoint, testes, CR-011
- [x] Script de produção ensaiado numa cópia do banco local
- [ ] Contrato (dono: colar o CR-011 nos dois repos) e web (mostrar IDH e governador no cartão do estado)
