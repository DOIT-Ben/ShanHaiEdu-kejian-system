"""Provider-neutral material parsing contract and deterministic test adapter."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

EVIDENCE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "material-evidence-package.schema.json"
)


@dataclass(frozen=True, slots=True)
class ParseLimits:
    max_file_bytes: int = 52_428_800
    max_pages: int = 500
    max_text_chars: int = 5_000_000
    max_image_references: int = 10_000
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if (
            min(
                self.max_file_bytes,
                self.max_pages,
                self.max_text_chars,
                self.max_image_references,
            )
            <= 0
        ):
            raise ValueError("material parse limits must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("material parse timeout must be positive")


@dataclass(frozen=True, slots=True)
class MaterialParseSource:
    file_asset_version_id: UUID
    sha256: str
    mime_type: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class MaterialParseResult:
    evidence: dict[str, Any]
    page_count: int
    text_checksum: str
    validation_report: dict[str, Any]


class MaterialParserError(RuntimeError):
    def __init__(self, code: str, message: str = "Material PDF parsing failed.") -> None:
        super().__init__(message)
        self.code = code


class MaterialParser(Protocol):
    name: str
    version: str

    def parse(
        self,
        path: Path,
        source: MaterialParseSource,
        limits: ParseLimits,
    ) -> MaterialParseResult: ...


class FakeMaterialParser:
    name = "fake-material-parser"
    version = "1.0"

    def __init__(
        self,
        *,
        page_texts: tuple[str, ...] = ("Deterministic material page",),
        error_code: str | None = None,
    ) -> None:
        if not page_texts:
            raise ValueError("fake material parser requires at least one page")
        self._page_texts = page_texts
        self._error_code = error_code

    def parse(
        self,
        path: Path,
        source: MaterialParseSource,
        limits: ParseLimits,
    ) -> MaterialParseResult:
        del path
        if self._error_code is not None:
            raise MaterialParserError(self._error_code)
        if len(self._page_texts) > limits.max_pages:
            raise MaterialParserError("PDF_PAGE_LIMIT_EXCEEDED")
        if sum(map(len, self._page_texts)) > limits.max_text_chars:
            raise MaterialParserError("PDF_TEXT_LIMIT_EXCEEDED")
        pages = [
            {
                "page_number": page_number,
                "text_blocks": [
                    {
                        "block_id": f"p{page_number}-text-1",
                        "text": text,
                        "text_checksum": _text_checksum(text),
                        "bbox": None,
                    }
                ]
                if text
                else [],
                "image_references": [],
            }
            for page_number, text in enumerate(self._page_texts, start=1)
        ]
        return build_parse_result(
            source=source,
            parser_name=self.name,
            parser_version=self.version,
            pages=pages,
            page_texts=list(self._page_texts),
        )


def build_parse_result(
    *,
    source: MaterialParseSource,
    parser_name: str,
    parser_version: str,
    pages: list[dict[str, Any]],
    page_texts: list[str],
) -> MaterialParseResult:
    evidence: dict[str, Any] = {
        "schema_version": "material-evidence-package.v1",
        "source": {
            "file_asset_version_id": str(source.file_asset_version_id),
            "sha256": source.sha256,
            "mime_type": source.mime_type,
            "byte_size": source.byte_size,
        },
        "parser": {"name": parser_name, "version": parser_version},
        "pages": pages,
    }
    report = validate_evidence_package(evidence)
    if not report["valid"]:
        raise MaterialParserError("PDF_EVIDENCE_INVALID")
    return MaterialParseResult(
        evidence=evidence,
        page_count=len(pages),
        text_checksum=_text_checksum("\f".join(page_texts)),
        validation_report=report,
    )


def validate_evidence_package(evidence: dict[str, Any]) -> dict[str, Any]:
    iter_errors = cast(
        Callable[[object], Iterable[ValidationError]],
        _evidence_validator().iter_errors,  # pyright: ignore[reportUnknownMemberType]
    )
    errors = sorted(
        iter_errors(evidence),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    return {
        "valid": not errors,
        "schema_version": "material-evidence-package.v1",
        "errors": [
            {
                "path": "/".join(str(part) for part in error.absolute_path),
                "validator": str(error.validator),
            }
            for error in errors
        ],
    }


@lru_cache(maxsize=1)
def _evidence_validator() -> Draft202012Validator:
    schema = json.loads(EVIDENCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _text_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
