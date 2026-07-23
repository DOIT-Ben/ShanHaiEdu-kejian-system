#!/usr/bin/env python3
"""Validate the full-chain contract freeze used by parallel development tracks."""

from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_NODE_SEQUENCES: dict[str, list[str]] = {
    "mainline": [
        "material.file_validate",
        "material.parse",
        "material.scope_review",
        "lesson.division.generate",
        "lesson.division.validate",
        "lesson.division.approve",
        "lesson_plan.generate",
        "lesson_plan.validate",
        "lesson_plan.approve",
        "intro.generate_options",
        "intro.validate",
        "intro.approve",
        "intro.select",
    ],
    "ppt": [
        "ppt.content_analyze",
        "ppt.outline.generate",
        "ppt.outline.approve",
        "ppt.pages.generate",
        "ppt.cover.prompt.generate",
        "ppt.cover.image.generate",
        "ppt.cover.approve",
        "ppt.style_contract.build",
        "ppt.body_asset_prompts.generate",
        "ppt.body_assets.generate",
        "ppt.pages.assemble",
        "pptx.export",
        "ppt.final.validate",
        "ppt.final.approve",
    ],
    "video": [
        "video.master_script.generate",
        "video.master_script.approve",
        "video.rough_storyboard.generate",
        "video.rough_storyboard.approve",
        "video.style_master.prompt.generate",
        "video.style_master.image.generate",
        "video.style_master.approve",
        "video.asset_inventory.generate",
        "video.asset_prompts.generate",
        "video.assets.generate",
        "video.fine_storyboard.generate",
        "video.shots.generate",
        "video.clips.select",
        "audio.plan.generate",
        "audio.tts.generate",
        "audio.subtitles.compile",
        "video.timeline.assemble",
        "video.classroom_quality.evaluate",
        "video.technical.validate",
        "video.final.approve",
    ],
    "delivery": ["delivery.package"],
}

REQUIRED_STATE_MODEL = {
    "queued",
    "running",
    "provider_succeeded",
    "draft",
    "submitted",
    "quality_failed",
    "awaiting_approval",
    "approved",
    "adopted",
    "saved_to_project",
    "stale",
}

VIDEO_FORBIDDEN_INPUT_KEYS = {
    "approved_lesson_plan_version_id",
    "lesson_plan_content_hash",
    "material_parse_version_id",
    "material_scope_artifact_version_id",
    "ppt_outline_version_id",
    "ppt_page_specs_version_id",
}

CORE_CONSUMER_READ_PATHS = {
    "contracts/api-surface.openapi.yaml",
    "contracts/generated/**",
    "contracts/full-chain-freeze.json",
    "contracts/page-api-fact-matrix.json",
    "contracts/fixtures/contract-freeze/**",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML object: {path}")
    return data


def _operation_ids(document: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    paths = document.get("paths", {})
    if not isinstance(paths, dict):
        return found
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if isinstance(operation_id, str):
                found.add(operation_id)
    return found


def _pattern_matches_or_contains(pattern: str, candidate: str) -> bool:
    if fnmatch.fnmatch(candidate, pattern) or fnmatch.fnmatch(pattern, candidate):
        return True
    prefix = pattern.removesuffix("/**").rstrip("/")
    other = candidate.removesuffix("/**").rstrip("/")
    return prefix == other or prefix.startswith(f"{other}/") or other.startswith(f"{prefix}/")


def _check_freeze_catalog(root: Path, errors: list[str]) -> None:
    freeze = _load_json(root / "contracts/full-chain-freeze.json")
    source_files = freeze["source_files"]
    catalog = _load_json(root / source_files["workflow_catalog"])
    manifest = _load_json(root / source_files["content_manifest"])

    if freeze.get("contract_version") != "shanhai.full-chain-freeze/v1":
        errors.append("full-chain freeze version is not v1")
    if freeze.get("status") != "frozen_for_parallel_development":
        errors.append("full-chain freeze is not marked frozen_for_parallel_development")
    if freeze["source_release"]["semantic_version"] != catalog.get("semantic_version"):
        errors.append("freeze release does not match workflow catalog release")
    if freeze["source_release"]["semantic_version"] != manifest.get("semantic_version"):
        errors.append("freeze release does not match content manifest release")
    if freeze["source_release"]["package_key"] != manifest.get("package_key"):
        errors.append("freeze package key does not match content manifest")

    catalog_nodes = catalog.get("nodes", [])
    if len(catalog_nodes) != 48:
        errors.append(f"workflow catalog must contain exactly 48 nodes, found {len(catalog_nodes)}")
    node_by_key = {node.get("node_key"): node for node in catalog_nodes if isinstance(node, dict)}
    if len(node_by_key) != len(catalog_nodes):
        errors.append("workflow catalog contains missing or duplicate node_key values")

    manifest_keys = {
        item.get("item_key")
        for item in manifest.get("items", [])
        if isinstance(item, dict) and isinstance(item.get("item_key"), str)
    }
    branches = {branch["branch_key"]: branch for branch in freeze.get("branches", [])}
    if set(branches) != set(EXPECTED_NODE_SEQUENCES):
        errors.append("freeze branches must be exactly mainline, ppt, video, and delivery")

    frozen_nodes: list[str] = []
    for branch_key, expected_sequence in EXPECTED_NODE_SEQUENCES.items():
        branch = branches.get(branch_key)
        if branch is None:
            continue
        actual_sequence = [entry.get("node_key") for entry in branch["required_node_sequence"]]
        if actual_sequence != expected_sequence:
            errors.append(f"{branch_key} node sequence differs from the frozen complete chain")
        for entry in branch["required_node_sequence"]:
            node_key = entry["node_key"]
            frozen_nodes.append(node_key)
            node = node_by_key.get(node_key)
            if node is None:
                errors.append(f"frozen node missing from workflow catalog: {node_key}")
                continue
            if node.get("execution_kind") != entry.get("expected_execution_kind"):
                errors.append(f"execution kind mismatch for {node_key}")
            if node.get("execution_scope") != entry.get("expected_scope"):
                errors.append(f"execution scope mismatch for {node_key}")
            if node.get("execution_kind") == "model_generation":
                template = node.get("generation_template_ref", {}).get("item_key")
                if not isinstance(template, str) or template not in manifest_keys:
                    errors.append(f"model node lacks published GenerationTemplate: {node_key}")
    if len(frozen_nodes) != len(set(frozen_nodes)):
        errors.append("a workflow node appears in more than one frozen branch")
    if set(frozen_nodes) != set(node_by_key):
        missing = sorted(set(node_by_key) - set(frozen_nodes))
        extra = sorted(set(frozen_nodes) - set(node_by_key))
        errors.append(
            f"freeze must cover the exact 48-node catalog; missing={missing}, extra={extra}"
        )

    lesson_plan = node_by_key.get("lesson_plan.generate", {})
    if lesson_plan.get("execution_scope") != "lesson_unit":
        errors.append("lesson_plan.generate must remain lesson_unit scoped")
    intro = node_by_key.get("intro.generate_options", {})
    forbidden = set(intro.get("context_policy", {}).get("forbidden_sources", []))
    if "lesson_plan.approved_version" not in forbidden:
        errors.append("intro generation must forbid lesson-plan context")

    ppt_entry = node_by_key.get("ppt.content_analyze", {})
    ppt_inputs = set(ppt_entry.get("input_contract_refs", []))
    required_ppt_inputs = {"approval:lesson_plan", "content:material_evidence"}
    if not required_ppt_inputs.issubset(ppt_inputs):
        errors.append("PPT entry must consume exact approved lesson plan and material evidence")

    video_entry = node_by_key.get("video.master_script.generate", {})
    if video_entry.get("input_contract_refs") != ["selection:intro"]:
        errors.append("video entry must consume only selection:intro")
    video_forbidden = set(video_entry.get("context_policy", {}).get("forbidden_sources", []))
    required_forbidden = {
        "lesson_plan.approved_version",
        "material.approved_parse",
        "ppt_outline.approved_version",
    }
    if not required_forbidden.issubset(video_forbidden):
        errors.append(
            "video entry must forbid lesson plan, material parse, and PPT outline context"
        )

    timeline = node_by_key.get("video.timeline.assemble", {})
    required_timeline_dependencies = {
        "video.clips.select",
        "audio.subtitles.compile",
    }
    if not required_timeline_dependencies.issubset(set(timeline.get("dependencies", []))):
        errors.append("video timeline must depend on formal clips and compiled subtitles")
    final_approval = node_by_key.get("video.final.approve", {})
    if final_approval.get("output_contract_refs") != ["approval:video_final"]:
        errors.append("complete video chain must terminate in approval:video_final")
    delivery = node_by_key.get("delivery.package", {})
    required_delivery_inputs = {
        "approval:lesson_plan",
        "artifact:intro_option_set",
        "approval:ppt_final",
        "approval:video_final",
    }
    if not required_delivery_inputs.issubset(set(delivery.get("input_contract_refs", []))):
        errors.append("delivery package must consume all approved lesson outputs")


def _check_page_matrix(root: Path, errors: list[str]) -> None:
    matrix = _load_json(root / "contracts/page-api-fact-matrix.json")
    active_ids = _operation_ids(_load_yaml(root / "contracts/api-surface.openapi.yaml"))
    planned_ids = _operation_ids(_load_yaml(root / "contracts/planned-api-surface.openapi.yaml"))

    if not REQUIRED_STATE_MODEL.issubset(set(matrix.get("state_model", []))):
        errors.append("frontend state model omits required formal states")
    operations = matrix.get("operations", [])
    operation_by_id = {entry.get("operation_id"): entry for entry in operations}
    if len(operation_by_id) != len(operations):
        errors.append("page API matrix contains duplicate operation IDs")
    for operation_id, entry in operation_by_id.items():
        availability = entry.get("availability")
        if availability == "active" and operation_id not in active_ids:
            errors.append(f"matrix declares missing active operation: {operation_id}")
        if availability == "planned" and operation_id not in planned_ids:
            errors.append(f"matrix declares missing planned operation: {operation_id}")
        if availability == "candidate_required" and operation_id in active_ids:
            errors.append(
                f"candidate operation is already active and matrix must be updated: {operation_id}"
            )

    for page in matrix.get("pages", []):
        route = page.get("route", "")
        scope_keys = set(page.get("scope_keys", []))
        if ":lessonId" in route and "lesson_id" not in scope_keys:
            errors.append(f"lesson page omits lesson_id scope: {page.get('page_key')}")
        for operation_id in page.get("refresh_operations", []):
            if operation_id not in operation_by_id:
                errors.append(f"page references undeclared refresh operation: {operation_id}")
        for action in page.get("actions", []):
            for operation_id in action.get("operation_ids", []):
                if operation_id not in operation_by_id:
                    errors.append(f"action references undeclared operation: {operation_id}")
            exact_references = set(action.get("exact_references", []))
            if ":lessonId" in route and "lesson_id" not in exact_references:
                errors.append(f"lesson action omits exact lesson_id: {action.get('action_key')}")
            lowered = " ".join(action.get("exact_references", [])).lower()
            if "latest" in lowered:
                errors.append(
                    "action uses a latest reference instead of exact version: "
                    f"{action.get('action_key')}"
                )

    forbidden = set(matrix.get("forbidden_frontend_behaviors", []))
    required_forbidden = {
        "call_provider_directly",
        "consume_planned_operation_as_active",
        "handwrite_duplicate_business_dto",
        "persist_formal_business_state_in_local_storage",
        "select_project_latest_artifact_without_lesson_and_exact_version",
    }
    if not required_forbidden.issubset(forbidden):
        errors.append("page API matrix omits required forbidden frontend behaviors")


def _check_two_lesson_fixture_data(fixture: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lessons = fixture.get("lessons", [])
    if len(lessons) < 2:
        return ["contract-freeze fixture must contain at least two lessons"]
    project_id = fixture.get("project", {}).get("project_id")
    seen: dict[str, set[str]] = {
        "lesson_id": set(),
        "lesson_unit_key": set(),
        "lesson_plan_version": set(),
        "intro_version": set(),
        "intro_selection": set(),
    }
    for lesson in lessons:
        lesson_id = lesson.get("lesson_id")
        lesson_key = lesson.get("lesson_unit_key")
        plan = lesson.get("lesson_plan", {})
        intro = lesson.get("intro", {})
        ppt_input = lesson.get("parallel_inputs", {}).get("ppt", {})
        video_input = lesson.get("parallel_inputs", {}).get("video", {})
        values = {
            "lesson_id": lesson_id,
            "lesson_unit_key": lesson_key,
            "lesson_plan_version": plan.get("artifact_version_id"),
            "intro_version": intro.get("artifact_version_id"),
            "intro_selection": intro.get("selection_id"),
        }
        for label, value in values.items():
            if not isinstance(value, str) or not value:
                errors.append(f"lesson has missing {label}")
            elif value in seen[label]:
                errors.append(f"duplicate {label}: {value}")
            else:
                seen[label].add(value)
        if plan.get("approval_status") != "approved":
            errors.append(f"lesson plan is not approved for {lesson_id}")
        if intro.get("approval_status") != "approved":
            errors.append(f"intro option set is not approved for {lesson_id}")
        if ppt_input.get("project_id") != project_id or ppt_input.get("lesson_id") != lesson_id:
            errors.append(f"PPT input scope mismatch for {lesson_id}")
        if ppt_input.get("approved_lesson_plan_version_id") != plan.get("artifact_version_id"):
            errors.append(f"PPT input does not use owner lesson plan version for {lesson_id}")
        if video_input.get("project_id") != project_id or video_input.get("lesson_id") != lesson_id:
            errors.append(f"video input scope mismatch for {lesson_id}")
        if video_input.get("intro_selection_id") != intro.get("selection_id"):
            errors.append(f"video input does not use owner IntroSelection for {lesson_id}")
        if video_input.get("intro_option_set_version_id") != intro.get("artifact_version_id"):
            errors.append(f"video input does not use owner option-set version for {lesson_id}")
        forbidden = VIDEO_FORBIDDEN_INPUT_KEYS.intersection(video_input)
        if forbidden:
            errors.append(
                f"video input leaks forbidden course context for {lesson_id}: {sorted(forbidden)}"
            )
    return errors


def _check_two_lesson_fixture(root: Path, errors: list[str]) -> None:
    fixture_path = root / "contracts/fixtures/contract-freeze/primary-math-two-lessons.json"
    fixture = _load_json(fixture_path)
    errors.extend(_check_two_lesson_fixture_data(fixture))


def _check_leases(root: Path, errors: list[str]) -> None:
    leases = _load_json(root / "contracts/development-leases.json")
    tracks = {track.get("track_key"): track for track in leases.get("tracks", [])}
    required_tracks = {"shared_contract", "frontend", "ppt", "video", "mainline"}
    if set(tracks) != required_tracks:
        errors.append(
            "development leases must define shared_contract, frontend, ppt, video, and mainline"
        )
        return

    shared_paths = leases.get("shared_contract_paths", [])
    shared_writer = tracks["shared_contract"]
    for path in shared_paths:
        if not any(
            _pattern_matches_or_contains(pattern, path) for pattern in shared_writer["writable"]
        ):
            errors.append(f"shared-contract owner does not cover shared path: {path}")

    consumer_keys = required_tracks - {"shared_contract"}
    for track_key in consumer_keys:
        track = tracks[track_key]
        if track.get("contract_change_required") is not True:
            errors.append(f"consumer track must require Contract Change: {track_key}")
        for writable in track.get("writable", []):
            for shared in shared_paths:
                if _pattern_matches_or_contains(writable, shared):
                    errors.append(
                        f"consumer track writes shared contract path: {track_key} -> {writable}"
                    )
        readable = track.get("readonly", []) + track.get("forbidden", [])
        for required_path in CORE_CONSUMER_READ_PATHS:
            if not any(
                _pattern_matches_or_contains(pattern, required_path) for pattern in readable
            ):
                errors.append(
                    "consumer track does not protect core contract path: "
                    f"{track_key} -> {required_path}"
                )

    consumers = [tracks[key] for key in sorted(consumer_keys)]
    for index, left in enumerate(consumers):
        for right in consumers[index + 1 :]:
            for left_path in left.get("writable", []):
                for right_path in right.get("writable", []):
                    if _pattern_matches_or_contains(left_path, right_path):
                        errors.append(
                            "parallel writable paths overlap: "
                            f"{left['track_key']}:{left_path} and "
                            f"{right['track_key']}:{right_path}"
                        )


def validate_contract_freeze(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required_files = [
        "contracts/full-chain-freeze.schema.json",
        "contracts/full-chain-freeze.json",
        "contracts/page-api-fact-matrix.schema.json",
        "contracts/page-api-fact-matrix.json",
        "contracts/development-leases.schema.json",
        "contracts/development-leases.json",
        "contracts/fixtures/contract-freeze/primary-math-two-lessons.json",
        "docs/governance/CONTRACT_FREEZE.md",
    ]
    for relative in required_files:
        if not (root / relative).is_file():
            errors.append(f"missing contract-freeze file: {relative}")
    if errors:
        return errors
    try:
        _check_freeze_catalog(root, errors)
        _check_page_matrix(root, errors)
        _check_two_lesson_fixture(root, errors)
        _check_leases(root, errors)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        errors.append(f"contract-freeze document is malformed: {exc}")
    return errors


def main() -> int:
    errors = validate_contract_freeze()
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("full-chain contract freeze checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
