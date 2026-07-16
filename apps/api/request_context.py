"""Request correlation context shared by middleware and logging."""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def resolve_request_id(candidate: str | None) -> str:
    if candidate and _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return f"req_{uuid.uuid4().hex}"
