from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from apps.api.assets.ppt_runtime_contracts import PptBackgroundFact
from apps.api.ppt_runtime.layout import build_assembly_request
from scripts.golden_courseware_ppt_outputs import build_golden_ppt_stage_outputs
from tests.unit.ppt_rendering.helpers import png_bytes

ROOT = Path(__file__).resolve().parents[3]


def test_golden_layout_keeps_editable_text_in_dedicated_safe_bands() -> None:
    case = cast(
        dict[str, Any],
        json.loads(
            (
                ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"
            ).read_text(encoding="utf-8")
        ),
    )
    content = build_golden_ppt_stage_outputs(case)["ppt.pages.generate"]
    payload = png_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    backgrounds = tuple(
        PptBackgroundFact(
            page_key=f"PAGE-{position:02d}",
            position=position,
            slot_key=f"ppt.page-{position:02d}.main-visual",
            binding_id=uuid4(),
            file_asset_id=uuid4(),
            file_asset_version_id=uuid4(),
            storage_bucket="test",
            storage_key=f"page-{position:02d}.png",
            mime_type="image/png",
            size_bytes=len(payload),
            sha256=digest,
            width=160,
            height=90,
        )
        for position in range(1, 11)
    )
    request = build_assembly_request(
        content,
        backgrounds,
        {background.file_asset_version_id: payload for background in backgrounds},
    )

    cover_title = request.pages[0].elements[0]
    assert cover_title.box.x > request.canvas.width // 2
    for page in request.pages[1:]:
        title = next(item for item in page.elements if item.element_key.endswith("teaching_task"))
        editable = [
            item
            for item in page.elements
            if not item.element_key.endswith(("backplate", "teaching_task"))
        ]
        assert title.box.y + title.box.height < min(item.box.y for item in editable)
        assert all(item.box.y >= 5_074_920 for item in editable)

    diagram_markers = [
        item
        for page in request.pages
        for item in page.elements
        if item.element_key.startswith("PPT-DIAGRAM-") and not item.element_key.endswith(".label")
    ]
    assert diagram_markers
    assert all(item.box.width == 365_760 for item in diagram_markers)
