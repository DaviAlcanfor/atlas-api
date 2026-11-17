"""POST /v1/chat (spec 025, CR-012 proposal): SSE answer from the Atlas chatbot. Logic in atlas_api/chat.py."""
from typing import Annotated, Literal

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from atlas_api import chat
from atlas_api.config import get_settings
from atlas_api.errors import problem

router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=4000)]


class ChatIn(BaseModel):
    messages: Annotated[list[ChatMessage], Field(min_length=1, max_length=20)]

    @field_validator("messages")
    @classmethod
    def _ends_with_user(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        if v[-1].role != "user":
            raise ValueError("the last message must be from the user")
        return v


def client_ip(request: Request) -> str:
    # ponytail: last X-Forwarded-For hop = the address the platform proxy saw (the client cannot forge that one,
    # only prepend); assumes exactly one proxy in front, as on FastAPI Cloud.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "?"


@router.post("/chat", response_model=None, responses={200: {"content": {"text/event-stream": {}}}})
def post_chat(body: ChatIn, request: Request) -> Response:
    st = get_settings()
    key = st.ai_gateway_api_key.get_secret_value() if st.ai_gateway_api_key else ""
    if not key:
        return problem(503, "O chat não está configurado neste servidor.", "Chat indisponível")
    refusal = chat.limiter.hit(client_ip(request), st.chat_per_ip_hour, st.chat_per_day)
    if refusal:
        return problem(429, refusal, "Limite do chat atingido")
    events = chat.answer([m.model_dump() for m in body.messages], key, request.app.state.session_factory,
                         st.chat_max_tool_rounds, st.chat_max_output_tokens)
    return StreamingResponse(events, media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
