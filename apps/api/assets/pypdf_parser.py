"""Timeout-bounded local PDF parser backed by pypdf.

API references:
https://pypdf.readthedocs.io/en/latest/user/encryption-decryption.html
https://pypdf.readthedocs.io/en/latest/user/extract-text.html
https://pypdf.readthedocs.io/en/latest/user/extract-images.html
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import socket
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from apps.api.assets.material_parser import (
    MaterialParserError,
    MaterialParseResult,
    MaterialParseSource,
    ParseLimits,
    build_parse_result,
    validate_evidence_package,
)

STABLE_PDF_ERRORS = frozenset(
    {
        "PDF_DAMAGED",
        "PDF_DANGEROUS_STRUCTURE",
        "PDF_ENCRYPTED",
        "PDF_EVIDENCE_INVALID",
        "PDF_IMAGE_REFERENCE_LIMIT_EXCEEDED",
        "PDF_PAGE_LIMIT_EXCEEDED",
        "PDF_TEXT_BLOCK_LIMIT_EXCEEDED",
        "PDF_TEXT_LIMIT_EXCEEDED",
    }
)


class PypdfMaterialParser:
    name = "pypdf"
    version = version("pypdf")

    def parse(
        self,
        path: Path,
        source: MaterialParseSource,
        limits: ParseLimits,
    ) -> MaterialParseResult:
        _validate_source(path, source, limits)
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-m", __name__, "--child"],
                input=json.dumps(
                    _child_request(path, source, limits, self.name, self.version)
                ).encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=limits.timeout_seconds,
                check=False,
                close_fds=True,
                cwd=Path(__file__).resolve().parents[3],
                env=_child_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            raise MaterialParserError("PDF_PARSE_TIMEOUT") from exc
        if completed.returncode != 0:
            raise MaterialParserError("PDF_DAMAGED")
        return _decode_child_response(completed.stdout, source)


def _validate_source(path: Path, source: MaterialParseSource, limits: ParseLimits) -> None:
    if source.mime_type.lower().split(";", maxsplit=1)[0].strip() != "application/pdf":
        raise MaterialParserError("PDF_MIME_UNSUPPORTED")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise MaterialParserError("PDF_SOURCE_UNAVAILABLE") from exc
    if size > limits.max_file_bytes or source.byte_size > limits.max_file_bytes:
        raise MaterialParserError("PDF_SIZE_LIMIT_EXCEEDED")
    if size != source.byte_size:
        raise MaterialParserError("PDF_SIZE_MISMATCH")
    try:
        with path.open("rb") as stream:
            signature = stream.read(5)
            stream.seek(0)
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as exc:
        raise MaterialParserError("PDF_SOURCE_UNAVAILABLE") from exc
    if signature != b"%PDF-":
        raise MaterialParserError("PDF_SIGNATURE_INVALID")
    if digest != source.sha256:
        raise MaterialParserError("PDF_CHECKSUM_MISMATCH")


def _child_main() -> int:
    _disable_network()
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        source = MaterialParseSource(
            file_asset_version_id=UUID(request["source"]["file_asset_version_id"]),
            sha256=request["source"]["sha256"],
            mime_type=request["source"]["mime_type"],
            byte_size=request["source"]["byte_size"],
        )
        limits = ParseLimits(**request["limits"])
        result = _parse_pdf(
            Path(request["path"]),
            source=source,
            limits=limits,
            parser_name=request["parser_name"],
            parser_version=request["parser_version"],
        )
    except MaterialParserError as exc:
        response: dict[str, Any] = {"kind": "error", "code": exc.code}
    except (PdfReadError, OSError, TypeError, ValueError, KeyError):
        response = {"kind": "error", "code": "PDF_DAMAGED"}
    except Exception:
        response = {"kind": "error", "code": "PDF_DAMAGED"}
    else:
        response = {
            "kind": "result",
            "result": {
                "evidence": result.evidence,
                "page_count": result.page_count,
                "text_checksum": result.text_checksum,
                "validation_report": result.validation_report,
            },
        }
    sys.stdout.buffer.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
    return 0


def _parse_pdf(
    path: Path,
    *,
    source: MaterialParseSource,
    limits: ParseLimits,
    parser_name: str,
    parser_version: str,
) -> MaterialParseResult:
    reader = PdfReader(path, strict=True)
    if reader.is_encrypted:
        raise MaterialParserError("PDF_ENCRYPTED")
    page_count = len(reader.pages)
    if page_count == 0:
        raise MaterialParserError("PDF_DAMAGED")
    if page_count > limits.max_pages:
        raise MaterialParserError("PDF_PAGE_LIMIT_EXCEEDED")
    _reject_dangerous_structures(reader)
    pages: list[dict[str, Any]] = []
    page_texts: list[str] = []
    text_char_count = 0
    text_block_count = 0
    image_reference_count = 0
    for page_number, page in enumerate(reader.pages, start=1):
        _reject_dangerous_page(page)
        blocks: list[dict[str, Any]] = []

        def visit_text(
            text: str,
            _current_matrix: Any,
            text_matrix: Any,
            _font_dictionary: Any,
            _font_size: Any,
            _blocks: list[dict[str, Any]] = blocks,
            _page_number: int = page_number,
        ) -> None:
            nonlocal text_block_count
            if not text:
                return
            if text_block_count >= limits.max_text_blocks:
                raise MaterialParserError("PDF_TEXT_BLOCK_LIMIT_EXCEEDED")
            text_block_count += 1
            _blocks.append(
                {
                    "block_id": f"p{_page_number}-text-{len(_blocks) + 1}",
                    "text": text,
                    "text_checksum": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "bbox": _point_bbox(text_matrix),
                }
            )

        text = page.extract_text(visitor_text=visit_text) or ""
        if text and not blocks:
            if text_block_count >= limits.max_text_blocks:
                raise MaterialParserError("PDF_TEXT_BLOCK_LIMIT_EXCEEDED")
            text_block_count += 1
            blocks.append(
                {
                    "block_id": f"p{page_number}-text-1",
                    "text": text,
                    "text_checksum": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "bbox": None,
                }
            )
        evidence_text = "".join(str(block["text"]) for block in blocks)
        text_char_count += len(evidence_text)
        if text_char_count > limits.max_text_chars:
            raise MaterialParserError("PDF_TEXT_LIMIT_EXCEEDED")
        image_names: list[str] = []
        for name in page.images.keys():
            image_reference_count += 1
            if image_reference_count > limits.max_image_references:
                raise MaterialParserError("PDF_IMAGE_REFERENCE_LIMIT_EXCEEDED")
            image_names.append(str(name))
        pages.append(
            {
                "page_number": page_number,
                "text_blocks": blocks,
                "image_references": [
                    {
                        "image_id": f"p{page_number}-image-{index}",
                        "object_name": name[:512],
                        "kind": "embedded",
                    }
                    for index, name in enumerate(image_names, start=1)
                ],
            }
        )
        page_texts.append(evidence_text)
    return build_parse_result(
        source=source,
        parser_name=parser_name,
        parser_version=parser_version,
        pages=pages,
        page_texts=page_texts,
    )


def _reject_dangerous_structures(reader: PdfReader) -> None:
    root = reader.root_object
    if any(name in root for name in ("/OpenAction", "/AA")):
        raise MaterialParserError("PDF_DANGEROUS_STRUCTURE")
    names = root.get("/Names")
    if names is not None:
        resolved_names = names.get_object()
        if any(name in resolved_names for name in ("/JavaScript", "/EmbeddedFiles")):
            raise MaterialParserError("PDF_DANGEROUS_STRUCTURE")
    form = root.get("/AcroForm")
    if form is not None and "/XFA" in form.get_object():
        raise MaterialParserError("PDF_DANGEROUS_STRUCTURE")


def _reject_dangerous_page(page: Any) -> None:
    if "/AA" in page:
        raise MaterialParserError("PDF_DANGEROUS_STRUCTURE")
    annotations = cast(list[Any], page.get("/Annots") or [])
    for annotation_reference in annotations:
        annotation = annotation_reference.get_object()
        if annotation.get("/Subtype") in {"/FileAttachment", "/RichMedia"}:
            raise MaterialParserError("PDF_DANGEROUS_STRUCTURE")
        action = annotation.get("/A")
        if action is not None and action.get_object().get("/S") in {
            "/ImportData",
            "/JavaScript",
            "/Launch",
            "/SubmitForm",
        }:
            raise MaterialParserError("PDF_DANGEROUS_STRUCTURE")


def _point_bbox(text_matrix: Any) -> list[float] | None:
    try:
        x = float(text_matrix[4])
        y = float(text_matrix[5])
    except (IndexError, TypeError, ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return [x, y, x, y]


def _child_request(
    path: Path,
    source: MaterialParseSource,
    limits: ParseLimits,
    parser_name: str,
    parser_version: str,
) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "source": {
            "file_asset_version_id": str(source.file_asset_version_id),
            "sha256": source.sha256,
            "mime_type": source.mime_type,
            "byte_size": source.byte_size,
        },
        "limits": {
            "max_file_bytes": limits.max_file_bytes,
            "max_pages": limits.max_pages,
            "max_text_chars": limits.max_text_chars,
            "max_text_blocks": limits.max_text_blocks,
            "max_image_references": limits.max_image_references,
            "timeout_seconds": limits.timeout_seconds,
        },
        "parser_name": parser_name,
        "parser_version": parser_version,
    }


def _child_environment() -> dict[str, str]:
    allowed = ("SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "LANG")
    environment = {name: os.environ[name] for name in allowed if name in os.environ}
    environment.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    return environment


def _disable_network() -> None:
    def denied(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("network access is disabled in the PDF parser")

    socket.socket = denied  # pyright: ignore[reportAssignmentType]
    socket.create_connection = denied  # pyright: ignore[reportAssignmentType]


def _decode_child_response(payload: bytes, source: MaterialParseSource) -> MaterialParseResult:
    try:
        response = json.loads(payload.decode("utf-8"))
        if response["kind"] == "error":
            code = str(response["code"])
            raise MaterialParserError(code if code in STABLE_PDF_ERRORS else "PDF_DAMAGED")
        result = response["result"]
        raw_evidence = result["evidence"]
        raw_validation_report = result["validation_report"]
        if not isinstance(raw_evidence, dict) or not isinstance(raw_validation_report, dict):
            raise TypeError("invalid parser result objects")
        evidence = cast(dict[str, Any], raw_evidence)
        page_count = int(result["page_count"])
        text_checksum = str(result["text_checksum"])
        validation_report = cast(dict[str, Any], raw_validation_report)
    except MaterialParserError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise MaterialParserError("PDF_DAMAGED") from exc
    report = validate_evidence_package(evidence)
    expected_source = evidence.get("source", {})
    if (
        not report["valid"]
        or page_count != len(evidence.get("pages", []))
        or expected_source.get("file_asset_version_id") != str(source.file_asset_version_id)
        or expected_source.get("sha256") != source.sha256
        or len(text_checksum) != 64
        or any(character not in "0123456789abcdef" for character in text_checksum)
    ):
        raise MaterialParserError("PDF_EVIDENCE_INVALID")
    return MaterialParseResult(
        evidence=evidence,
        page_count=page_count,
        text_checksum=text_checksum,
        validation_report=validation_report,
    )


if __name__ == "__main__":
    raise SystemExit(_child_main())
