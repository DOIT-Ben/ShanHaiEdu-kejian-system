from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from apps.api.assets.project_contracts import SEMANTIC_KEY_PATTERN
from scripts.golden_courseware_ppt_outputs import build_golden_ppt_runtime_page_facts

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


def test_golden_runtime_projection_preserves_the_exact_ten_page_facts() -> None:
    case = cast(dict[str, Any], json.loads(GOLDEN.read_text(encoding="utf-8")))
    pages = build_golden_ppt_runtime_page_facts(case)

    assert [page["page_key"] for page in pages] == [f"PAGE-{index:02d}" for index in range(1, 11)]
    assert [page["position"] for page in pages] == list(range(1, 11))
    assert [page["background_slot"] for page in pages] == [
        page["asset_requirements"][0]["target_slot"] for page in case["ppt"]["page_specs"]
    ]
    assert all(
        re.fullmatch(SEMANTIC_KEY_PATTERN, cast(str, page["background_slot"]))
        for page in pages
    )
    assert [page["editable_elements"] for page in pages] == [
        page["editable_elements"] for page in case["ppt"]["page_specs"]
    ]
    assert all(len(page["editable_elements"]) >= 1 for page in pages)
    assert all(page["source_page_spec_set_key"] == "PPT-PAGE-SPECS-001" for page in pages)
