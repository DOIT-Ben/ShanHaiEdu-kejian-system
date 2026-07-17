from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from pypdf import PdfWriter

from apps.api.assets.material_parser import MaterialParserError, MaterialParseSource, ParseLimits
from apps.api.assets.pypdf_parser import PypdfMaterialParser, _child_environment


def build_pdf(path: Path, *, pages: int, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if encrypted:
        writer.encrypt("secret")
    with path.open("wb") as output:
        writer.write(output)
    return path.read_bytes()


def parse_source(payload: bytes) -> MaterialParseSource:
    import hashlib

    return MaterialParseSource(
        file_asset_version_id=UUID("019a0000-0000-7000-8000-000000000002"),
        sha256=hashlib.sha256(payload).hexdigest(),
        mime_type="application/pdf",
        byte_size=len(payload),
    )


def test_real_local_parser_reads_generated_multi_page_pdf(tmp_path: Path) -> None:
    path = tmp_path / "generated.pdf"
    payload = build_pdf(path, pages=3)

    result = PypdfMaterialParser().parse(
        path,
        parse_source(payload),
        ParseLimits(max_pages=5, timeout_seconds=10),
    )

    assert result.page_count == 3
    assert [page["page_number"] for page in result.evidence["pages"]] == [1, 2, 3]
    assert result.validation_report["valid"] is True


@pytest.mark.parametrize(
    ("pages", "encrypted", "limits", "expected"),
    [
        (2, False, ParseLimits(max_pages=1), "PDF_PAGE_LIMIT_EXCEEDED"),
        (1, True, ParseLimits(), "PDF_ENCRYPTED"),
    ],
)
def test_real_local_parser_rejects_unsafe_or_oversized_documents(
    tmp_path: Path,
    pages: int,
    encrypted: bool,
    limits: ParseLimits,
    expected: str,
) -> None:
    path = tmp_path / "rejected.pdf"
    payload = build_pdf(path, pages=pages, encrypted=encrypted)

    with pytest.raises(MaterialParserError) as error:
        PypdfMaterialParser().parse(path, parse_source(payload), limits)

    assert error.value.code == expected


def test_real_local_parser_rejects_damaged_pdf(tmp_path: Path) -> None:
    path = tmp_path / "damaged.pdf"
    payload = b"%PDF-this-is-not-a-document"
    path.write_bytes(payload)

    with pytest.raises(MaterialParserError) as error:
        PypdfMaterialParser().parse(path, parse_source(payload), ParseLimits())

    assert error.value.code == "PDF_DAMAGED"


@pytest.mark.parametrize(
    ("source_change", "limits", "expected"),
    [
        ({"mime_type": "text/plain"}, ParseLimits(), "PDF_MIME_UNSUPPORTED"),
        ({"sha256": "0" * 64}, ParseLimits(), "PDF_CHECKSUM_MISMATCH"),
        ({"byte_size": 1}, ParseLimits(), "PDF_SIZE_MISMATCH"),
        ({}, ParseLimits(max_file_bytes=1), "PDF_SIZE_LIMIT_EXCEEDED"),
    ],
)
def test_real_local_parser_validates_source_metadata_before_parsing(
    tmp_path: Path,
    source_change: dict[str, object],
    limits: ParseLimits,
    expected: str,
) -> None:
    path = tmp_path / "source-validation.pdf"
    payload = build_pdf(path, pages=1)
    source = replace(parse_source(payload), **source_change)

    with pytest.raises(MaterialParserError) as error:
        PypdfMaterialParser().parse(path, source, limits)

    assert error.value.code == expected


def test_real_local_parser_rejects_invalid_pdf_signature(tmp_path: Path) -> None:
    path = tmp_path / "invalid-signature.pdf"
    payload = b"not-a-pdf"
    path.write_bytes(payload)

    with pytest.raises(MaterialParserError) as error:
        PypdfMaterialParser().parse(path, parse_source(payload), ParseLimits())

    assert error.value.code == "PDF_SIGNATURE_INVALID"


def test_real_local_parser_rejects_javascript_actions(tmp_path: Path) -> None:
    path = tmp_path / "javascript.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_js("app.alert('unsafe')")
    with path.open("wb") as output:
        writer.write(output)
    payload = path.read_bytes()

    with pytest.raises(MaterialParserError) as error:
        PypdfMaterialParser().parse(path, parse_source(payload), ParseLimits())

    assert error.value.code == "PDF_DANGEROUS_STRUCTURE"


def test_real_local_parser_terminates_subprocess_at_timeout(tmp_path: Path) -> None:
    path = tmp_path / "timeout.pdf"
    payload = build_pdf(path, pages=1)

    with pytest.raises(MaterialParserError) as error:
        PypdfMaterialParser().parse(
            path,
            parse_source(payload),
            ParseLimits(timeout_seconds=0.001),
        )

    assert error.value.code == "PDF_PARSE_TIMEOUT"


def test_parser_child_environment_does_not_inherit_provider_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-reach-parser")
    monkeypatch.setenv("SHANHAI_OBJECT_STORAGE_SECRET_KEY", "must-not-reach-parser")

    environment = _child_environment()

    assert "OPENROUTER_API_KEY" not in environment
    assert "SHANHAI_OBJECT_STORAGE_SECRET_KEY" not in environment
    assert environment["PYTHONUTF8"] == "1"
