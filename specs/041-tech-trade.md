# 041 - Tecnologia e chips por país (onda 4, B13)
Status: approved (dono, 2026-11-18: "faz o resto") | BLOQUEADA por lacuna de dado (ver abaixo); nenhuma rota escrita |
Contrato: CR-017 NÃO escrita (o delta depende da decisão abaixo) | Origem: B13 do PLAN | Relacionada: 029

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
Regra do dono: sem baixar arquivos grandes. Nada foi baixado. (Observação: o zip HS22 de 301 MB JÁ está em
`etl_cache/baci/BACI_HS22_V202601.zip` do checkout principal; reagregar dele não exige download.)

### `TX.VAL.TECH.MF.ZS`
Já está no ETL do Banco Mundial (`etl/worldbank/pipeline.py`, "Exportações: alta tecnologia", % das exportações de
manufaturados; a descrição do pedido diz "industriais", o rótulo do indicador é "manufaturados") e em `queries.py`; sai pelo
catálogo `GET /v1/indicators` e pelo perfil. Não precisa de rota nova.

## Opções para destravar (decisão do dono)
A. **Recomendada**: estender o ETL `etl baci` (lendo o zip já em cache) para gravar, por país e para os 6 HS4, exportação e
   importação (valor, parte do total, top 5 parceiros) em tabela aditiva `country_tech_trade` (migração 0NNN aditiva, 1 linha por
   país x HS4 x fluxo, JSONB só nos parceiros), `import-trade` a preenche; rota `GET /v1/countries/{iso2}/tech`. Sem fonte nova.
B. Só o que já existe: devolver os HS4 que por acaso estão no top 10 de exportação. Não recomendado (lacuna acima).

## Contract delta (proposta para A; CR-017 só será escrita após a decisão)
```
GET /v1/countries/{iso2}/tech -> {
  year: int,
  products: [{ hs: string, label: string (pt-BR, MDIC), flow: "export"|"import", value_usd: float, share: float,
               partners: [{ iso2: string, value_usd: float, share: float }] }],   // até 6 produtos x 2 fluxos; partners até 5
  sources: [Source]
}
```
404 para iso2 desconhecido; país sem dado = `products: []`.

## Tarefas
- [x] Inspecionar o que o BACI importado guarda (lacuna registrada acima)
- [ ] Dono escolhe A ou B
- [ ] ETL + migração aditiva + `import-trade` + rota + testes + CR-017 + OpenAPI
- [ ] Web
