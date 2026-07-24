from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from workflow.content_package import validate_content_package
from workflow.node_generation_binding import validate_workflow_node_catalog

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
SOURCE_PATH = ROOT / "workflow/builtin/primary_math_courseware/generation-source.json"
CATALOG_PATH = (
    CONTRACTS / "fixtures/workflow-node-generation-bindings/primary-math-courseware.json"
)
PACKAGE_PATH = CONTRACTS / "fixtures/primary-math-courseware-package"


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _node(catalog: dict[str, Any], key: str) -> dict[str, Any]:
    return next(node for node in catalog["nodes"] if node["node_key"] == key)


def _template(source: dict[str, Any], key: str) -> dict[str, Any]:
    return next(node for node in source["nodes"] if node["template_key"] == key)


def test_video_golden_node_is_the_minimal_1_5_entrypoint() -> None:
    source = _object(SOURCE_PATH)
    catalog = _object(CATALOG_PATH)
    package = validate_content_package(PACKAGE_PATH, contracts_root=CONTRACTS)
    validated = validate_workflow_node_catalog(
        catalog,
        schema=_object(CONTRACTS / "workflow-node-generation-binding.schema.json"),
    )

    assert source["package"]["semantic_version"] == "1.5.0"
    assert package.manifest["semantic_version"] == "1.5.0"
    assert catalog["semantic_version"] == "1.5.0"
    assert validated.catalog["semantic_version"] == "1.5.0"

    node = _node(catalog, "video.shots.generate")
    assert node["dependencies"] == []
    assert node["entrypoint"] is True
    assert node["input_contract_refs"] == ["selection:intro"]
    assert node["context_policy"] == {
        "mode": "declared",
        "allowed_sources": ["intro_selection.snapshot"],
        "forbidden_sources": [
            "lesson_plan.approved_version",
            "material.approved_parse",
            "ppt_outline.approved_version",
        ],
    }
    assert node["reference_asset_policy"] == {
        "mode": "required",
        "roles": [
            {
                "role_key": "shot_keyframe",
                "requirement": "required",
                "media_types": ["image"],
                "min_items": 1,
                "max_items": 1,
                "order_mode": "stable_by_role_then_version",
                "allowed_sources": ["asset_slot_current"],
                "provider_exposure": ["signed_url"],
            }
        ],
    }
    assert node["output_persistence"]["artifact"]["relations"] == []
    downstream_master = _node(catalog, "video.master_script.generate")
    assert downstream_master["dependencies"] == ["video.shots.generate"]
    assert downstream_master["entrypoint"] is False


def test_video_golden_template_freezes_one_candidate_and_the_release_style() -> None:
    source = _object(SOURCE_PATH)
    template = _template(source, "video.shots.generate")
    fields = {field["field_key"]: field for field in template["input"]["fields"]}

    assert template["style_preset_refs"] == ["style.primary_math.paper_clay"]
    assert set(fields) == {
        "selected_intro_ref",
        "shot_candidate_count",
        "shot_duration_seconds",
        "shot_reference_assets",
        "shot_style_preset",
    }
    assert fields["shot_candidate_count"]["default_value"] == 1
    assert fields["shot_candidate_count"]["validation"] == {"minimum": 1, "maximum": 1}
    assert fields["shot_duration_seconds"]["default_value"] == 6
    assert fields["shot_duration_seconds"]["validation"] == {"minimum": 6, "maximum": 6}
    assert fields["shot_style_preset"]["default_value"] == "style.primary_math.paper_clay"
    assert template["prompt"]["context_bindings"] == [
        {
            "binding_key": "selected_intro",
            "source": "intro_selection.snapshot",
            "required": True,
            "exposure": "full",
            "max_items": 1,
            "max_bytes": 100000,
        }
    ]
