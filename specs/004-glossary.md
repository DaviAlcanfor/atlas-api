# 004 — Regime de todos os países + glossário
Status: done (aguardando contrato v1.1) | Contrato: v1.1 | Web: atlas-web/specs/004-glossary.md

## Por quê
O web quer explicar *como funciona* cada regime (tooltip + popup + catálogo). Hoje **191 de 196 países têm `regime` null**
(só os 5 do seed legado), então primeiro é preciso preencher regime, depois escrever os verbetes.

## Dados
1. Regime: Wikidata P122 ("basic form of government", CC0) na pipeline do Wikidata. Valores são Q-ids
   (ex.: Q1756 "sistema presidencialista"). `content/regimes.yaml` mapeia Q-id → `regime_id` + rótulo pt-BR.
   País com vários P122 (ex.: "república" + "sistema parlamentarista") → o mapa define combinações; Q-id sem mapa = null + relatório.
   O seed legado (5 países) passa a ser sobrescrito pelo Wikidata? → decisão abaixo.
2. Verbetes: `content/glossary.yaml`, texto próprio (não copiado), revisado pelo dono, com fontes por verbete.
   Catálogo inicial = regimes distintos que sairem do passo 1 + regiões (`region`) + organizações (`memberships`).

## Contract delta
```
GlossaryTerm { id, kind: "regime"|"system"|"region"|"membership"|"currency"|"other", label, short, body,
               icon: string|null, examples: string[] /* iso2 */, sources: Source[] }
CountrySummary/CountryDetail += regime_id: string|null
GET /v1/glossary -> { items: GlossaryTerm[] }        GET /v1/glossary/{id} -> GlossaryTerm
```

## Design
- Migração: tabela `glossary_terms`; coluna `countries.regime_id` (FK).
- `import-content` lê `glossary.yaml` (idempotente, mesma transação). `examples` = query (países com o mesmo `regime_id`, ordenados por nome, máx. 8).
- `has_content` não muda.

## Tarefas
- [x] P122 no ETL + `regimes.yaml` + relatório de Q-ids sem mapa (abaixo)
- [x] rascunho de `glossary.yaml` para revisão (13 regimes + 7 regiões + ONU; RASCUNHO, revisão humana pendente)
- [x] migração 0003, import, endpoints, testes

## Decisões abertas
1. ~~Regime do Wikidata sobrescreve o texto do seed legado?~~ Decidido 2026-11-11: sim (quando há `regime_id`).
2. Quem escreve os verbetes? (recomendado: agente rascunha com fonte, dono revisa.)

## Relatório P122 (2026-11-11, `python -m etl wikidata`)
**153/196 países com `regime_id`.** Distribuição: república parlamentarista 38, república (genérico: o Wikidata só diz
"república") 32, república presidencialista 29, monarquia constitucional 28, semipresidencialista 12, monarquia absoluta 4,
partido único 3, teocracia 2, e 1 cada: república islâmica, república popular, junta militar, sistema diretorial,
governo provisório.
- Sem P122 no Wikidata (37): CF CR DJ DM DO ER FJ GD GQ GW HT JM JO KE KI MH ML MV MW MZ NA NE NR PG PW PY SB SC ST TD TG TO TV TZ VU WS ZW
- P122 sem regra ou contraditório (6): AE (constitucional + absoluta), BE (só "federação"), CU (só "Estado unitário"),
  GE e TN (semi + presidencialista), GH (só "democracia")
- Q-ids sem mapa (ignorados de propósito): Q179164 Estado unitário (19 países), Q188759 democracia representativa (9),
  Q43702 federação (5), Q7174 democracia (GH TW), Q11409 apartheid (ZA, erro), Q48349 império (MX, erro),
  Q17023307 democracia Herrenvolk (LR, histórico), Q181800 Juche, Q5433328 ditadura familiar (KP), Q189898 emirado (AF),
  Q4204060 Estado islâmico (BN), Q584683 monarquia eletiva (MY), Q849242 monarquia hereditária (MC), Q12774933 papado (VA),
  Q936648 diarquia (SM), Q310988 democracia participativa (UY). Os marcados "erro"/"histórico" valem correção no Wikidata.
- Escolhas do mapa para revisar: US e IN ficam "república" (o Wikidata não diz presidencialista/parlamentarista);
  NP fica "república" (tem "república popular" + "república federal"; a regra genérica vem antes); AD = monarquia
  constitucional (coprincipado); BH e QA = monarquia constitucional (é o que o Wikidata diz).
