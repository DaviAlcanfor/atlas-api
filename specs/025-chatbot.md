# 025 - Chatbot do Atlas (API)
Status: in progress (API pronta em PR; falta CR-012 no contrato + secret no FastAPI Cloud) | Contrato: CR-012 | Web: atlas-web/specs/025-chatbot.md

## Decisões do dono (citadas da spec do web, aprovada em 2026-11-17)
- "a chave do chatbot é a mesma que já tá no projeto, do AI Gateway ... só deixo usar o gpt 6 luna ... dale"
- Chave: a do AI Gateway que já está no projeto (`AI_GATEWAY_API_KEY`).
- Modelo: só `openai/gpt-6-luna`. Qualquer outro precisa de aprovação. (Sem modelo reserva, nem em teste.)
- Teto de gasto: não informado; valem os limites abaixo até o dono mudar.

## Dados (upstream: Vercel AI Gateway, docs lidas em 2026-11-17)
- Endpoint OpenAI-compatível: `POST https://ai-gateway.vercel.sh/v1/chat/completions`, `Authorization: Bearer $AI_GATEWAY_API_KEY`
  (página "OpenAI Chat Completions Requests"). Parâmetros usados: `model`, `messages`, `stream`, `tools`, `tool_choice`,
  `max_completion_tokens` ("If you set both `max_tokens` and `max_completion_tokens`, AI Gateway uses `max_completion_tokens`").
- Streaming (página "Streaming"): "Each data line starts with `data:` followed by JSON, except the final `data: [DONE]` line";
  "AI Gateway can send SSE comment lines that start with `:` (for example, `: heartbeat`) ... ignore these lines";
  "Content is delivered incrementally in the `delta.content` field".
- Ferramentas (página "Tool Calling"): "This follows the same specification as the OpenAI Function Calling API": definição
  `{type: "function", function: {name, description, parameters}}`, resposta com `tool_calls[{id, type, function{name, arguments}}]`
  e `finish_reason: "tool_calls"`. No streaming, pela mesma especificação OpenAI, os `delta.tool_calls` chegam em pedaços
  agrupados por `index` (id e nome no primeiro, `arguments` em fragmentos de texto JSON). O resultado volta como
  `{role: "tool", tool_call_id, content}`.
- Preço do modelo (citado em `etl/ai/summaries.py`): ~US$ 0,10 / 0,50 por milhão de tokens de entrada / saída.

## Desenho
- `POST /v1/chat` (SSE). Lógica em `src/atlas_api/chat.py`, rota em `routers/chat.py`. `httpx` (já vem com `fastapi[standard]`), sem dependência nova.
- Ferramentas = funções de `queries.py` chamadas no processo (uma sessão curta do banco por chamada): `search`, `list_countries`
  (filtro por região/regime), `get_country` (sem linha do tempo/idiomas), `get_leaders` (mais recentes primeiro), `get_people`,
  `get_profile`, `get_economy`, `get_trade`, `get_history`, `get_languages`, `get_currency`, `glossary`, `list_indicators`,
  `indicator_ranking` (top N, asc/desc, ou só alguns países). Resultado de ferramenta cortado em 32 mil caracteres.
- Prompt de sistema em pt-BR: só o que as ferramentas trouxeram, fonte de cada número, "o Atlas não tem esse dado", links `/pais/xx`.
- `countries`: os ISO2 dos links `/pais/xx` da resposta que existem no Atlas (o globo voa até eles).
- `done.sources`: os `Source` que vieram nos resultados das ferramentas usadas (sem repetir).
- Nada é guardado no servidor: o navegador manda o histórico inteiro a cada pergunta.

## Contract delta (CR-012)
Ver `contract/CHANGE_REQUESTS.md` CR-012.

## Limites (variáveis de ambiente; padrão)
`CHAT_PER_IP_HOUR` 20, `CHAT_PER_DAY` 300, `CHAT_MAX_TOOL_ROUNDS` 6, `CHAT_MAX_OUTPUT_TOKENS` 1200 (por chamada ao modelo; as
rodadas de ferramenta só geram o JSON da chamada). Corpo: até 20 mensagens, 1 a 4000 caracteres cada, a última do usuário.
Contador em memória, por processo: se o FastAPI Cloud rodar N réplicas, o teto real é N vezes maior (spec 019 não conseguiu fixar
réplicas). IP = último salto do `X-Forwarded-For` (o que o proxy da plataforma viu).

## Tarefas
- [x] Docs do AI Gateway lidas e citadas
- [x] `POST /v1/chat` SSE + ferramentas + prompt pt-BR
- [x] Limites (IP/hora, dia, rodadas, tokens) + 429/503 problem+json em pt-BR
- [x] CORS: `POST` liberado (preflight testado; `CORS_ORIGINS` continua sendo a lista de origens)
- [x] Testes com gateway falso (texto, rodada de ferramenta, 429, 422, 503, erro do gateway, CORS)
- [x] Teste manual local contra o gateway real (só `openai/gpt-6-luna`): 4 ferramentas, resposta com fontes e links
- [x] CR-012 escrita
- [ ] Dono: CR-012 no contrato dos dois repos
- [ ] Dono: `AI_GATEWAY_API_KEY` (secret) no FastAPI Cloud (hoje NÃO está lá)
