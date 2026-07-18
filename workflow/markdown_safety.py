"""Shared safety checks for imported and administrator-edited Markdown."""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urlparse

from markdown_it import MarkdownIt
from markdown_it.token import Token

MAX_MARKDOWN_BYTES = 2_000_000
UNSAFE_LINK_SCHEMES = frozenset({"data", "file", "javascript", "vbscript"})


class MarkdownTemplateError(ValueError):
    """Raised when Markdown cannot safely become a template draft."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def decode_markdown_source(payload: bytes) -> str:
    """Decode bounded UTF-8 Markdown while rejecting unsafe controls."""

    if len(payload) > MAX_MARKDOWN_BYTES:
        raise MarkdownTemplateError(
            "MARKDOWN_TOO_LARGE",
            f"Markdown exceeds {MAX_MARKDOWN_BYTES} bytes",
        )
    try:
        source = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MarkdownTemplateError(
            "MARKDOWN_INVALID_UTF8",
            "Markdown must use UTF-8 encoding",
        ) from exc
    if not source.strip():
        raise MarkdownTemplateError("MARKDOWN_EMPTY", "Markdown cannot be empty")
    if "\x00" in source:
        raise MarkdownTemplateError(
            "MARKDOWN_UNSAFE_CONTROL",
            "Markdown contains an unsupported control character",
        )
    return source


def parse_safe_markdown(source: str) -> list[Token]:
    """Parse Markdown after applying the shared HTML, image, and link policy."""

    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    parser.validateLink = _accept_link_for_validation
    tokens = parser.parse(source)
    _validate_tokens(tokens)
    return tokens


def validate_markdown_fragment(source: str) -> None:
    """Revalidate edited draft Markdown before immutable compilation."""

    if not source.strip():
        return
    try:
        payload = source.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise MarkdownTemplateError(
            "MARKDOWN_INVALID_UTF8",
            "Markdown must use UTF-8 encoding",
        ) from exc
    decode_markdown_source(payload)
    parse_safe_markdown(source)


def _validate_tokens(tokens: list[Token]) -> None:
    for token in _walk_tokens(tokens):
        if token.type in {"html_block", "html_inline"}:
            raise MarkdownTemplateError(
                "MARKDOWN_UNSAFE_HTML",
                "Raw HTML is not supported in Markdown templates",
            )
        if token.type == "image":
            raise MarkdownTemplateError(
                "MARKDOWN_UNSUPPORTED_IMAGE",
                "Images are outside the Markdown adapter V1 scope",
            )
        if token.type == "link_open":
            raw_href = token.attrGet("href")
            href = raw_href if isinstance(raw_href, str) else ""
            if urlparse(href).scheme.lower() in UNSAFE_LINK_SCHEMES:
                raise MarkdownTemplateError(
                    "MARKDOWN_UNSAFE_LINK",
                    "Markdown contains an unsafe link scheme",
                )


def _accept_link_for_validation(url: str) -> bool:
    return True


def _walk_tokens(tokens: list[Token]) -> Iterator[Token]:
    pending = list(reversed(tokens))
    while pending:
        token = pending.pop()
        yield token
        if token.children:
            pending.extend(reversed(token.children))
