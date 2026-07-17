"""Timeout-bounded local PDF parser backed by pypdf."""

from __future__ import annotations

import hashlib
import math
import multiprocessing
from importlib.metadata import version
from pathlib import Path
from queue import Empty
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from apps.api.assets.material_parser import (
    MaterialParserError,
    MaterialParseResult,
    MaterialParseSource,
    ParseLimits,
    build_parse_result,
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
        context = multiprocessing.get_context("spawn")
        queue = context.Queue(maxsize=1)
        process = context.Process(
            target=_parse_in_subprocess,
            args=(str(path), source, limits, self.name, self.version, queue),
            daemon=True,
        )
        process.start()
        process.join(limits.timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
            queue.close()
            queue.join_thread()
            raise MaterialParserError("PDF_PARSE_TIMEOUT")
        try:
            kind, payload = queue.get(timeout=1)
        except Empty as exc:
            raise MaterialParserError("PDF_DAMAGED") from exc
        finally:
            queue.close()
            queue.join_thread()
        if kind == "error":
            raise MaterialParserError(str(payload))
        return payload


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


def _parse_in_subprocess(
    path: str,
    source: MaterialParseSource,
    limits: ParseLimits,
    parser_name: str,
    parser_version: str,
    queue: Any,
) -> None:
    try:
        result = _parse_pdf(
            Path(path),
            source=source,
            limits=limits,
            parser_name=parser_name,
            parser_version=parser_version,
        )
    except MaterialParserError as exc:
        queue.put(("error", exc.code))
    except (PdfReadError, OSError, TypeError, ValueError, KeyError):
        queue.put(("error", "PDF_DAMAGED"))
    else:
        queue.put(("result", result))


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
    image_reference_count = 0
    for page_number, page in enumerate(reader.pages, start=1):
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
            if not text:
                return
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
            blocks.append(
                {
                    "block_id": f"p{page_number}-text-1",
                    "text": text,
                    "text_checksum": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "bbox": None,
                }
            )
        text_char_count += len(text)
        if text_char_count > limits.max_text_chars:
            raise MaterialParserError("PDF_TEXT_LIMIT_EXCEEDED")
        image_names = [str(name) for name in page.images.keys()]
        image_reference_count += len(image_names)
        if image_reference_count > limits.max_image_references:
            raise MaterialParserError("PDF_IMAGE_REFERENCE_LIMIT_EXCEEDED")
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
        page_texts.append(text)
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


def _point_bbox(text_matrix: Any) -> list[float] | None:
    try:
        x = float(text_matrix[4])
        y = float(text_matrix[5])
    except (IndexError, TypeError, ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return [x, y, x, y]
