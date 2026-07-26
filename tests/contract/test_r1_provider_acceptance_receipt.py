from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/r1-provider-acceptance-receipt.schema.json"


def test_r1_provider_acceptance_receipt_schema_compiles_and_excludes_private_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    encoded = json.dumps(schema, sort_keys=True)
    for forbidden in (
        "api_key",
        "content_json",
        "error_details_json",
        "prompt",
        "raw_response",
        "secret",
        "snapshot_json",
    ):
        assert forbidden not in encoded
