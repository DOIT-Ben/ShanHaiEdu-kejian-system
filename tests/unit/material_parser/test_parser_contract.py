from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from apps.api.assets.material_parser import (
    FakeMaterialParser,
    MaterialParserError,
    MaterialParseSource,
    ParseLimits,
    validate_evidence_package,
)


def source() -> MaterialParseSource:
    return MaterialParseSource(
        file_asset_version_id=UUID("019a0000-0000-7000-8000-000000000001"),
        sha256="a" * 64,
        mime_type="application/pdf",
        byte_size=128,
    )


def test_fake_parser_is_deterministic_and_matches_evidence_schema(tmp_path: Path) -> None:
    pdf_path = tmp_path / "safe.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    parser = FakeMaterialParser(page_texts=("Page one", "Page two"))

    first = parser.parse(pdf_path, source(), ParseLimits())
    second = parser.parse(pdf_path, source(), ParseLimits())

    assert first == second
    assert first.page_count == 2
    assert first.text_checksum == second.text_checksum
    assert validate_evidence_package(first.evidence)["valid"] is True


def test_fake_parser_exposes_stable_error_codes(tmp_path: Path) -> None:
    parser = FakeMaterialParser(error_code="PDF_PARSE_TIMEOUT")

    with pytest.raises(MaterialParserError) as error:
        parser.parse(tmp_path / "ignored.pdf", source(), ParseLimits())

    assert error.value.code == "PDF_PARSE_TIMEOUT"
