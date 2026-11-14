# 022 - Resumo do país ("TL;DR")
Status: done (API) | Contrato: v1.5 (CR-007) | Web: atlas-web/specs/022-country-brief.md

## Pedido (2026-11-13)
"Um TL;DR do país: geografia + população + história + economia na primeira parte; e quando for falar do recente, sumarizar."
Decisão do dono no meio da implementação: "ao invés de resumir tudo com IA, faz uma espécie de f-string, uma fórmula com as
informações que já pegam da API, e só muda algumas coisas pra ficar mais fácil e não gastar muito" + "usa o GPT 6 Luna".

## Como funciona (`python -m etl ai-summaries`)
1. Fatos lidos da própria API do Atlas (país, perfil, economia, história, governantes): o resumo não diz nada que o site não mostre.
2. Fórmula (`template`): frases fixas em pt-BR preenchidas com os fatos, cada uma só quando o fato existe. Grátis.
3. Redação (`polish`): `openai/gpt-6-luna` pelo Vercel AI Gateway (US$ 0,10/0,50 por milhão de tokens) reescreve para ficar
   mais fluido. Só vale se todo número do texto novo já estiver no texto da fórmula; senão fica a fórmula.
4. Cache por hash: rodar de novo só paga os países que mudaram. 2026-11-13: 197/197 países com redação aprovada, ~9 min.
Fica para depois: a parte "acontecendo agora" com notícias (spec 008).

## Tarefas
- [x] ETL + testes (fórmula, números, guarda da redação)
- [x] migração 0016, `import-facts`, `GET /v1/countries/{iso2}/brief`, CR-007
