from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from apps.api.stage2_gate.preflight import (
    Stage2Budget,
    Stage2GateConfig,
    Stage2GatePreflightError,
    build_safe_console_summary,
    preflight_stage2_gate,
)
from pydantic import SecretStr
from pypdf import PdfWriter

from apps.api.model_gateway.contracts import ModelUsage
from apps.api.settings import Settings


def _textbook(tmp_path: Path, *, pages: int = 2) -> tuple[Path, str]:
    path = tmp_path / "authorized-textbook.pdf"
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as output:
        writer.write(output)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _settings(**updates: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "environment": "test",
        "database_url": SecretStr("postgresql+psycopg://stage2@localhost/stage2"),
        "object_storage_endpoint": "localhost:9000",
        "object_storage_access_key": SecretStr("stage2-access"),
        "object_storage_secret_key": SecretStr("stage2-secret"),
        "text_provider_name": "newapi",
        "text_provider_base_url": "https://provider.invalid/v1",
        "text_provider_model": "deepseek-v3",
        "text_provider_secret_env": "STAGE2_GATE_TEST_KEY",
    }
    values.update(updates)
    return Settings(**values)


def _config(
    tmp_path: Path,
    textbook_path: Path,
    textbook_sha256: str,
    **updates: object,
) -> Stage2GateConfig:
    values: dict[str, object] = {
        "real": True,
        "textbook_path": textbook_path,
        "authorized_textbook_sha256": textbook_sha256,
        "page_start": 1,
        "page_end": 2,
        "max_cost_usd": Decimal("25"),
        "evidence_dir": tmp_path / "runtime" / "evidence",
        "allow_minimax_fallback": False,
    }
    values.update(updates)
    return Stage2GateConfig(**values)


def test_preflight_requires_explicit_real_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    textbook, digest = _textbook(tmp_path)
    monkeypatch.setenv("STAGE2_GATE_TEST_KEY", "configured")

    with pytest.raises(Stage2GatePreflightError, match="STAGE2_REAL_FLAG_REQUIRED"):
        preflight_stage2_gate(_config(tmp_path, textbook, digest, real=False), _settings())


def test_preflight_requires_the_exact_authorized_textbook_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    textbook, digest = _textbook(tmp_path)
    monkeypatch.setenv("STAGE2_GATE_TEST_KEY", "configured")

    with pytest.raises(Stage2GatePreflightError, match="STAGE2_TEXTBOOK_UNAUTHORIZED"):
        preflight_stage2_gate(_config(tmp_path, textbook, "0" * 64), _settings())

    assert digest != "0" * 64


@pytest.mark.parametrize(
    ("page_start", "page_end", "code"),
    [
        (0, 1, "STAGE2_PAGE_RANGE_INVALID"),
        (2, 1, "STAGE2_PAGE_RANGE_INVALID"),
        (1, 3, "STAGE2_PAGE_RANGE_OUT_OF_BOUNDS"),
    ],
)
def test_preflight_rejects_an_invalid_or_out_of_bounds_page_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    page_start: int,
    page_end: int,
    code: str,
) -> None:
    textbook, digest = _textbook(tmp_path)
    monkeypatch.setenv("STAGE2_GATE_TEST_KEY", "configured")

    with pytest.raises(Stage2GatePreflightError, match=code):
        preflight_stage2_gate(
            _config(
                tmp_path,
                textbook,
                digest,
                page_start=page_start,
                page_end=page_end,
            ),
            _settings(),
        )


def test_preflight_rejects_a_non_deepseek_primary_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    textbook, digest = _textbook(tmp_path)
    monkeypatch.setenv("STAGE2_GATE_TEST_KEY", "configured")

    with pytest.raises(Stage2GatePreflightError, match="STAGE2_PROVIDER_ROUTE_REJECTED"):
        preflight_stage2_gate(
            _config(tmp_path, textbook, digest),
            _settings(text_provider_model="unapproved-model"),
        )


def test_preflight_allows_minimax_only_with_the_explicit_fallback_switch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    textbook, digest = _textbook(tmp_path)
    monkeypatch.setenv("STAGE2_GATE_TEST_KEY", "configured")
    settings = _settings(text_provider_name="minimax", text_provider_model="MiniMax-Text-01")

    with pytest.raises(Stage2GatePreflightError, match="STAGE2_PROVIDER_ROUTE_REJECTED"):
        preflight_stage2_gate(_config(tmp_path, textbook, digest), settings)

    result = preflight_stage2_gate(
        _config(tmp_path, textbook, digest, allow_minimax_fallback=True),
        settings,
    )

    assert result.provider == "minimax"


@pytest.mark.parametrize(
    "missing_field",
    [
        "database_url",
        "object_storage_endpoint",
        "object_storage_access_key",
        "object_storage_secret_key",
    ],
)
def test_preflight_requires_postgres_and_object_storage_landings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
) -> None:
    textbook, digest = _textbook(tmp_path)
    monkeypatch.setenv("STAGE2_GATE_TEST_KEY", "configured")

    with pytest.raises(Stage2GatePreflightError, match="STAGE2_DATA_LANDING_MISSING"):
        preflight_stage2_gate(
            _config(tmp_path, textbook, digest),
            _settings(**{missing_field: None}),
        )


@pytest.mark.parametrize("maximum", [Decimal("0"), Decimal("-1"), Decimal("NaN")])
def test_preflight_requires_a_positive_finite_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    maximum: Decimal,
) -> None:
    textbook, digest = _textbook(tmp_path)
    monkeypatch.setenv("STAGE2_GATE_TEST_KEY", "configured")

    with pytest.raises(Stage2GatePreflightError, match="STAGE2_BUDGET_INVALID"):
        preflight_stage2_gate(
            _config(tmp_path, textbook, digest, max_cost_usd=maximum),
            _settings(),
        )


def test_budget_stops_on_unknown_or_excess_provider_cost() -> None:
    budget = Stage2Budget(Decimal("1"))

    with pytest.raises(Stage2GatePreflightError, match="STAGE2_PROVIDER_COST_UNKNOWN"):
        budget.record(ModelUsage(total_tokens=10, cost=None))

    budget.record(ModelUsage(total_tokens=10, cost=Decimal("0.75")))
    with pytest.raises(Stage2GatePreflightError, match="STAGE2_BUDGET_EXCEEDED"):
        budget.record(ModelUsage(total_tokens=10, cost=Decimal("0.26")))


def test_safe_summary_excludes_private_inputs_and_internal_identifiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    textbook, digest = _textbook(tmp_path)
    monkeypatch.setenv("STAGE2_GATE_TEST_KEY", "configured-secret-value")
    result = preflight_stage2_gate(_config(tmp_path, textbook, digest), _settings())

    summary = build_safe_console_summary(
        result,
        conclusion="passed",
        total_usage=ModelUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=Decimal("0.25"),
        ),
    )
    serialized = json.dumps(summary)

    assert set(summary) == {
        "conclusion",
        "utc",
        "provider",
        "model",
        "textbook_sha256",
        "page_range",
        "usage",
    }
    assert "configured-secret-value" not in serialized
    assert str(textbook) not in serialized
    assert "compiled_prompt" not in serialized
    assert "output_schema" not in serialized
    assert "project_id" not in serialized
    assert "artifact_version_id" not in serialized
    assert "node_run_id" not in serialized
