# 041 - Tecnologia e chips por país (onda 4, B13)
Status: in progress (aprovada pelo dono em 2026-11-18: "faz o resto"; opção A em PR) |
Contrato: CR-017 | Origem: B13 do PLAN | Relacionada: 029

## Pedido
Seção "Tecnologia e chips" por país, derivada do BACI **já no banco**, sem fonte nova: exportações e importações dos produtos
HS 8542 (circuitos integrados), 8471 (computadores), 8802 e 8803 (aeronaves e partes), 8541 (semicondutores) e 8517
(telefones/redes), com valor, ano, parte do total e principais parceiros; mais `TX.VAL.TECH.MF.ZS`.

## Dados (inspecionado em 2026-11-18; licença e fonte: as da spec 029, BACI/CEPII Etalab 2.0, versão 202601, HS22, ano 2024)
### O que `country_trade` guarda de fato
Uma linha por país: `exports_usd`, `imports_usd`, `top_exports` (JSONB, **só os 10 maiores produtos em HS de 4 dígitos**),
`top_destinations` e `top_origins` (10 maiores parceiros, **totais, sem produto**). Não há importação por produto, nem parceiro
por produto (`etl/baci/pipeline.py`, `TOP = 10`; `data_out/trade.json`).

### Lacuna
Os 6 códigos só aparecem se estiverem entre os 10 maiores produtos EXPORTADOS do país. Medido em `data_out/trade.json`
(225 países): 8542 em 23; 8471 em 20; 8802 em 20; 8541 em 7; 8517 em 36; **8803 em 0**. Importações por produto: **0 países**
(o campo não existe). Parceiros por produto: não existem. Servir isso como "tecnologia" faria quase todo país parecer sem
dado (ou, pior, passar por "não exporta chips"), o que seria inventar uma ausência.

### Não baixado
Regra do dono: sem baixar arquivos grandes. Nada foi baixado. O zip HS22 de 301 MB JÁ estava em `etl_cache/baci/`; a opção A reagrega dele.

### `TX.VAL.TECH.MF.ZS`
Já está no ETL do Banco Mundial (`etl/worldbank/pipeline.py`, "Exportações: alta tecnologia", % das exportações de
manufaturados; a descrição do pedido diz "industriais", o rótulo do indicador é "manufaturados") e em `queries.py`; sai pelo
catálogo `GET /v1/indicators` e pelo perfil. Não precisa de rota nova.

## Decisão (dono, 2026-11-18): opção A
Estender `etl baci` (lê o zip HS22 já em `etl_cache/baci/`, sem baixar nada); o `trade.json` ganha `tech` por país; `import-trade`
preenche a tabela nova `country_tech_trade` (migração 0024, ADITIVA: 1 linha por país, `products` em JSONB; o esquema migra sozinho
no deploy). Rótulos: os mesmos nomes pt-BR literais do MDIC/Secex (`NCM_SH.csv`, CC BY-ND 3.0, fonte `mdic-sh`, lida na 029).
Regras: valor do produto = soma dos fluxos do HS4 no ano; `share` = parte das exportações (ou importações) do país; parceiros =
até 5 por fluxo, `share` sobre o valor do produto naquele fluxo; parceiro sem ISO2 (p.ex. Taiwan = "Other Asia, nes" no BACI)
conta no valor, nunca aparece como parceiro.

## Contract delta (= CR-017)
```
GET /v1/countries/{iso2}/tech -> {
  year: int|null,
  products: [{ hs: "8542"|"8471"|"8802"|"8803"|"8541"|"8517", label: string (pt-BR, MDIC), flow: "export"|"import",
               value_usd: float, share: float,
               partners: [{ iso2: string, value_usd: float, share: float }] }],   // partners até 5
  sources: [Source]
}
```
404 para iso2 desconhecido; país sem dado no BACI (p.ex. TW) = `{year: null, products: [], sources: []}`.

## Tarefas
- [x] Inspecionar o que o BACI importado guarda (lacuna registrada acima)
- [x] Dono escolhe A (2026-11-18)
- [x] ETL + migração 0024 aditiva + `import-trade` + rota + testes + CR-017 + OpenAPI
- [ ] O dono cola a CR-017 no contrato dos 2 repos e roda `import-trade` em produção (ANTES do merge não é obrigatório: a rota responde vazio sem dados)
- [ ] Web
