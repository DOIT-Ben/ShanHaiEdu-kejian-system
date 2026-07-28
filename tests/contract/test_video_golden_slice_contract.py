from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ROOT / "contracts" / "api-surface.openapi.yaml"
PLANNED = ROOT / "contracts" / "planned-api-surface.openapi.yaml"
CATALOG = (
    ROOT
    / "contracts"
    / "fixtures"
    / "workflow-node-generation-bindings"
    / "primary-math-courseware.json"
)
GENERATION_SOURCE = (
    ROOT / "workflow" / "builtin" / "primary_math_courseware" / "generation-source.json"
)

VIDEO_OPERATIONS = {
    (
        "/projects/{project_id}/lessons/{lesson_id}/video",
        "get",
    ): "getLessonVideoGoldenSlice",
    (
        "/projects/{project_id}/lessons/{lesson_id}/video/generations",
        "post",
    ): "startLessonVideoGeneration",
    (
        "/projects/{project_id}/lessons/{lesson_id}/video/results/{result_id}/adoptions",
        "post",
    ): "adoptLessonVideoResult",
    (
        "/projects/{project_id}/lessons/{lesson_id}/video/adoptions/{adoption_id}/save",
        "post",
    ): "saveLessonVideoAdoption",
}


def test_video_golden_slice_is_active_and_not_planned() -> None:
    active = yaml.safe_load(ACTIVE.read_text(encoding="utf-8"))
    planned = yaml.safe_load(PLANNED.read_text(encoding="utf-8"))
    for (path, method), operation_id in VIDEO_OPERATIONS.items():
        assert active["paths"][path][method]["operationId"] == operation_id
        assert path not in planned.get("paths", {})


def test_video_snapshot_exposes_exact_candidate_file_and_adoption_facts() -> None:
    active = yaml.safe_load(ACTIVE.read_text(encoding="utf-8"))
    schemas = active["components"]["schemas"]
    snapshot = schemas["VideoGoldenSlice"]
    assert set(snapshot["required"]) >= {
        "project_id",
        "lesson_unit_id",
        "intro_selection_id",
        "keyframe_file_asset_version_id",
        "job",
        "candidate",
    }
    candidate = schemas["VideoGoldenSliceCandidate"]
    assert set(candidate["required"]) >= {
        "result_id",
        "file_asset_version_id",
        "mime_type",
        "byte_size",
        "sha256",
        "duration_ms",
        "playback_url",
        "adoption_id",
        "saved_binding_id",
    }


def test_release_1_6_makes_exact_single_keyframe_video_the_branch_entrypoint() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    source = json.loads(GENERATION_SOURCE.read_text(encoding="utf-8"))
    node = next(item for item in catalog["nodes"] if item["node_key"] == "video.shots.generate")
    source_node = next(
        item for item in source["nodes"] if item["template_key"] == "video.shots.generate"
    )

    assert catalog["semantic_version"] == "1.6.0"
    assert source["package"]["semantic_version"] == "1.6.0"
    assert node["dependencies"] == []
    assert node["entrypoint"] is True
    assert node["input_contract_refs"] == ["selection:intro", "asset:shot_keyframe"]
    assert node["context_policy"] == {
        "mode": "declared",
        "allowed_sources": ["intro_selection.snapshot"],
        "forbidden_sources": [
            "lesson_plan.approved_version",
            "material.approved_parse",
            "ppt_outline.approved_version",
            "video_fine_storyboard.approved_version",
        ],
    }
    assert node["reference_asset_policy"]["roles"] == [
        {
            "role_key": "shot_keyframe",
            "requirement": "required",
            "media_types": ["image"],
            "min_items": 1,
            "max_items": 1,
            "order_mode": "stable_by_role_then_version",
            "allowed_sources": ["asset_slot_current"],
            "provider_exposure": ["signed_url", "provider_file_id", "inline_bytes"],
        }
    ]
    assert source_node["style_preset_refs"] == ["style.primary_math.paper_clay"]
    candidate_count = next(
        field
        for field in source_node["input"]["fields"]
        if field["field_key"] == "shot_candidate_count"
    )
    assert candidate_count["source"] == "system"
    assert candidate_count["default_value"] == 1
    assert candidate_count["validation"] == {"minimum": 1, "maximum": 1}
