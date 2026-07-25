from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast
from uuid import uuid4

from jsonschema import Draft202012Validator

from tests.integration.r1_teacher_flow_support import (
    intro_output,
    lesson_plan_output,
    two_lesson_division_output,
)

MAX_REQUEST_BYTES = 1_000_000


def _provider_request_id() -> str:
    return f"r1-deterministic-http-{uuid4()}"


def build_structured_output(prompt: str) -> dict[str, Any]:
    context = _json_section(prompt, "context:declared_context")
    schema = _json_section(prompt, "output_schema:request_schema")
    required = _string_sequence(schema.get("required"))
    if "division_key" in required:
        output = two_lesson_division_output(_evidence_keys(context))
    elif "teaching_content" in required:
        unit = _lesson_unit(context)
        output = lesson_plan_output(unit, _lesson_index(unit))
    elif "option_set_key" in required:
        output = intro_output(_lesson_unit(context))
    else:
        raise ValueError("R1 deterministic provider received an unsupported request schema")

    errors = sorted(
        Draft202012Validator(schema).iter_errors(output),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise ValueError("R1 deterministic output does not satisfy the request schema")
    return output


def _json_section(prompt: str, label: str) -> dict[str, Any]:
    marker = f"[{label}]\n"
    start = prompt.find(marker)
    if start < 0:
        raise ValueError(f"compiled prompt is missing {label}")
    content_start = start + len(marker)
    content_end = prompt.find("\n\n[", content_start)
    raw = prompt[content_start:] if content_end < 0 else prompt[content_start:content_end]
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"compiled prompt contains invalid {label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"compiled prompt contains non-object {label}")
    return cast(dict[str, Any], value)


def _context_contents(context: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    bindings = context.get("bindings")
    if not isinstance(bindings, Sequence) or isinstance(bindings, (str, bytes, bytearray)):
        raise ValueError("declared context has no bindings")
    for binding in cast(Sequence[object], bindings):
        if not isinstance(binding, Mapping):
            continue
        items = binding.get("items")
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
            continue
        for item in cast(Sequence[object], items):
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if isinstance(content, Mapping):
                yield dict(cast(Mapping[str, Any], content))


def _evidence_keys(context: Mapping[str, Any]) -> list[str]:
    contents = tuple(_context_contents(context))
    for content in contents:
        keys = _string_sequence(content.get("approved_evidence_keys"))
        if len(keys) >= 2:
            return keys
    for content in contents:
        keys = _legacy_evidence_keys(content)
        if len(keys) >= 2:
            return keys
    for content in contents:
        keys = _page_evidence_keys(content)
        if len(keys) >= 2:
            return keys
    raise ValueError("declared context has fewer than two exact material evidence keys")


def _legacy_evidence_keys(content: Mapping[str, Any]) -> list[str]:
    evidence = content.get("material_evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes, bytearray)):
        return []
    keys: list[str] = []
    for raw in cast(Sequence[object], evidence):
        if isinstance(raw, Mapping):
            key = raw.get("evidence_key")
            if isinstance(key, str) and key:
                keys.append(key)
    return keys


def _page_evidence_keys(content: Mapping[str, Any]) -> list[str]:
    pages = content.get("pages")
    if not isinstance(pages, Sequence) or isinstance(pages, (str, bytes, bytearray)):
        return []
    keys: list[str] = []
    for raw_page in cast(Sequence[object], pages):
        if not isinstance(raw_page, Mapping):
            continue
        page = cast(Mapping[str, Any], raw_page)
        keys.extend(_mapping_keys(page.get("text_blocks"), "block_id"))
        keys.extend(_mapping_keys(page.get("image_references"), "image_id"))
    return keys


def _mapping_keys(value: object, key_name: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    keys: list[str] = []
    for raw in cast(Sequence[object], value):
        if isinstance(raw, Mapping):
            key = raw.get(key_name)
            if isinstance(key, str) and key:
                keys.append(key)
    return keys


def _lesson_unit(context: Mapping[str, Any]) -> dict[str, Any]:
    for content in _context_contents(context):
        unit = content.get("lesson_unit")
        if isinstance(unit, Mapping) and isinstance(unit.get("lesson_unit_key"), str):
            return dict(cast(Mapping[str, Any], unit))
        if isinstance(content.get("lesson_unit_key"), str):
            return content
    raise ValueError("declared context has no exact lesson unit")


def _lesson_index(unit: Mapping[str, Any]) -> int:
    key = unit.get("lesson_unit_key")
    if isinstance(key, str):
        suffix = key.rsplit("-", maxsplit=1)[-1]
        if suffix.isdigit():
            return max(1, int(suffix))
    return 1


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in cast(Sequence[object], value) if isinstance(item, str) and item]


class R1TextProviderRequestHandler(BaseHTTPRequestHandler):
    server_version = "ShanHaiR1Provider/1.0"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            payload = self._request_payload()
            prompt = self._prompt(payload)
            output = build_structured_output(prompt)
            model = payload.get("model")
            if not isinstance(model, str) or not model:
                raise ValueError("model is required")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            self._write_json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": {"metadata": {"error_type": "invalid_request"}}},
            )
            return
        self._write_json(
            HTTPStatus.OK,
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                output,
                                ensure_ascii=False,
                                separators=(",", ":"),
                                sort_keys=True,
                            )
                        },
                    }
                ],
                "id": _provider_request_id(),
                "model": model,
                "usage": {
                    "completion_tokens": 4,
                    "cost": 0,
                    "prompt_tokens": 8,
                    "total_tokens": 12,
                },
            },
        )

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _request_payload(self) -> dict[str, Any]:
        authorization = self.headers.get("Authorization", "")
        if (
            not authorization.startswith("Bearer ")
            or not authorization.removeprefix("Bearer ").strip()
        ):
            raise ValueError("authorization is required")
        raw_length = self.headers.get("Content-Length")
        if raw_length is None or not raw_length.isdigit():
            raise ValueError("content length is required")
        length = int(raw_length)
        if length < 1 or length > MAX_REQUEST_BYTES:
            raise ValueError("request body size is invalid")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request body must be an object")
        return cast(dict[str, Any], payload)

    @staticmethod
    def _prompt(payload: Mapping[str, Any]) -> str:
        messages = payload.get("messages")
        if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes, bytearray)):
            raise ValueError("messages are required")
        for message in reversed(cast(Sequence[object], messages)):
            if not isinstance(message, Mapping) or message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, str) and content:
                return content
        raise ValueError("user prompt is required")

    def _write_json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve deterministic R1 text outputs over HTTP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=58081, type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), R1TextProviderRequestHandler)
    print(f"r1_text_provider_stub_ready host={args.host} port={args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
