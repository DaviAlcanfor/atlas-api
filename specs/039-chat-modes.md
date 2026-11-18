# 039 - Chat: modos de resposta e evento `map` (parte da API)
Status: approved (dono, 2026-11-18; spec web: `geo/specs/039-chat-modos.md`) | Contrato: v1.10 + CR-016 | Web: spec 039 do front

## Por quê
O chat deve guiar a exploração. Um agente só, com modos; o servidor troca só o bloco de instruções do prompt de sistema.

## Requisitos
- `POST /v1/chat` aceita `mode` opcional: `"learn" | "analyse" | "tell"`. Valor desconhecido = 422. Sem `mode` = prompt de hoje, byte a byte.
- O modo vem SÓ do campo do request (nunca de texto do usuário, do modelo ou de tool). Tools e escopo não mudam.
- Aprender: etapas curtas, termina com 2-3 opções. Analisar: valor, ano, fonte, método, lacunas e limites. Narrar: só com conteúdo
  do Atlas; nunca rotas militares/batalhas sem dado; incerteza explícita.
- Evento SSE `map` `{iso2: string[], layer?: string, year?: int}`, só com `mode`. O modelo é instruído (nos blocos de modo) a citar
  `[texto](/mapa?camada=regime&ano=1700)`; o servidor lê esses links e só emite valores validados: `iso2` = países linkados que
  existem (`queries.country_exists`, mesma lista do evento `countries`), `year` inteiro em [YEAR_MIN, year_max()] e != 0,
  `layer` em `content|regime|flags|ranking`. Sem camada nem ano válidos, não há evento `map`. Nenhuma fonte de dado nova.

## Tarefas
- [x] spec, CR-016
- [x] `mode` no request, 3 blocos de prompt, evento `map`
- [x] `tests/test_chat_modes.py`
