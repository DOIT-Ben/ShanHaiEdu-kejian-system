from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from apps.api.assets.material_parser import (
    FakeMaterialParser,
    MaterialParserError,
    MaterialParseSource,
    ParseLimits,
    _resolve_evidence_schema_path,
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


def test_fake_parser_limits_text_block_count(tmp_path: Path) -> None:
    parser = FakeMaterialParser(page_texts=("First", "Second"))

    with pytest.raises(MaterialParserError) as error:
        parser.parse(tmp_path / "ignored.pdf", source(), ParseLimits(max_text_blocks=1))

    assert error.value.code == "PDF_TEXT_BLOCK_LIMIT_EXCEEDED"


def test_evidence_schema_resolution_supports_non_editable_runtime(tmp_path: Path) -> None:
    runtime_root = tmp_path / "app"
    runtime_prefix = runtime_root / ".venv"
    installed_module = (
        runtime_prefix
        / "lib"
        / "python3.12"
        / "site-packages"
        / "apps"
        / "api"
        / "assets"
        / "material_parser.py"
    )
    installed_module.parent.mkdir(parents=True)
    installed_module.touch()
    schema = runtime_root / "contracts" / "material-evidence-package.schema.json"
    schema.parent.mkdir(parents=True)
    schema.write_text("{}", encoding="utf-8")

    resolved = _resolve_evidence_schema_path(
        module_path=installed_module,
        runtime_prefix=runtime_prefix,
    )

    assert resolved == schema
