"""Chat tool logs (spec 038): which tools run and for which countries, never what the user wrote.

Only argument KEYS are stored; a value is kept only for the keys in VALUE_KEYS and only if it looks like an identifier
(the model fills free-text keys such as `q` with words from the user's question, so those stay value-less).
Retention: every insert also deletes rows older than RETENTION_DAYS (same transaction, no scheduled job).
"""
import logging
import re
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from atlas_api.db.models import ChatToolLog

log = logging.getLogger("atlas_api.chat_logs")
RETENTION_DAYS = 14
VALUE_KEYS = {"iso2", "code", "id", "order", "role", "limit", "countries"}
TOKEN = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")


def _token(v: Any) -> Any:
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    return v if isinstance(v, str) and TOKEN.match(v) else None


def sanitize(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in list(args.items())[:20]:
        k = str(k)[:40]
        if k not in VALUE_KEYS:
            out[k] = None
        elif isinstance(v, list):
            out[k] = [t for t in map(_token, v[:50]) if t is not None]
        else:
            out[k] = _token(v)
    return out


def record(factory: Callable[[], Session], tool: str, args: dict[str, Any], ok: bool) -> None:
    """Never raises: a logging failure must not break the chat answer."""
    try:
        with factory() as s, s.begin():
            s.add(ChatToolLog(tool=tool[:60], args=sanitize(args), ok=ok))
            s.execute(delete(ChatToolLog).where(ChatToolLog.ts < datetime.now(UTC) - timedelta(days=RETENTION_DAYS)))
    except Exception:
        log.warning("chat tool log not written", exc_info=True)


def parse_since(text: str) -> timedelta:
    m = re.fullmatch(r"(\d+)([dh])", text)
    if not m:
        raise ValueError("--since deve ser como 1d ou 6h")
    n = int(m[1])
    return timedelta(days=n) if m[2] == "d" else timedelta(hours=n)


def summary(s: Session, since: timedelta) -> dict[str, Any]:
    rows = s.execute(select(ChatToolLog.tool, ChatToolLog.args, ChatToolLog.ok)
                     .where(ChatToolLog.ts >= datetime.now(UTC) - since)).all()
    countries: Counter[str] = Counter()
    for _, args, _ in rows:
        countries.update(str(c).upper() for c in [args.get("iso2"), *(args.get("countries") or [])] if c)
    return {"calls": len(rows), "errors": sum(not ok for *_, ok in rows),
            "per_tool": Counter(t for t, *_ in rows).most_common(), "top_countries": countries.most_common(10)}
