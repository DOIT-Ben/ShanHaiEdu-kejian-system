"""Minimal structured logging with safe request correlation."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from apps.api.request_context import request_id_context

_STANDARD_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)
_STRUCTURED_HANDLER_MARKER = "_shanhaiedu_json_handler"


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service: str, environment: str) -> None:
        super().__init__()
        self._service = service
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service,
            "environment": self._environment,
            "message": record.getMessage(),
        }
        request_id = request_id_context.get()
        if request_id:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_FIELDS or key.startswith("_"):
                continue
            if isinstance(value, str | int | float | bool) or value is None:
                payload[key] = value
        if record.exc_info and record.exc_info[0]:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def configure_logging(*, service: str, environment: str, level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers:
        if getattr(handler, _STRUCTURED_HANDLER_MARKER, False):
            handler.setFormatter(JsonFormatter(service=service, environment=environment))
            handler.setLevel(level)
            return

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter(service=service, environment=environment))
    setattr(handler, _STRUCTURED_HANDLER_MARKER, True)
    root.addHandler(handler)
