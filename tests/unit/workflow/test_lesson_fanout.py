from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from apps.api.workflows.lesson_fanout import build_lesson_fanout_plan
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"


def test_fanout_plan_consumes_only_published_scope_branch_entrypoint_and_dependencies() -> None:
    payload = cast(dict[str, Any], json.loads(CATALOG.read_text(encoding="utf-8")))
    registered = BUILTIN_WORKFLOW_REGISTRY.load(payload)

    plans = build_lesson_fanout_plan(registered)

    assert [plan.branch_key for plan in plans] == [
        "intro_options",
        "lesson_plan",
        "ppt",
        "video",
    ]
    assert {plan.branch_key: plan.entrypoint_node_keys for plan in plans} == {
        "intro_options": ("intro.generate_options",),
        "lesson_plan": ("lesson_plan.generate",),
        "ppt": ("ppt.content_analyze",),
        "video": ("video.master_script.generate",),
    }
    assert all(plan.entrypoint_dependencies == ((),) for plan in plans)


def test_fanout_plan_tracks_renamed_entrypoint_without_node_key_or_phase_allowlist() -> None:
    payload = cast(dict[str, Any], json.loads(CATALOG.read_text(encoding="utf-8")))
    node = next(item for item in payload["nodes"] if item["node_key"] == "lesson_plan.generate")
    node["node_key"] = "renamed.lesson.entry"
    for candidate in payload["nodes"]:
        candidate["dependencies"] = [
            "renamed.lesson.entry" if value == "lesson_plan.generate" else value
            for value in candidate["dependencies"]
        ]
    registered = BUILTIN_WORKFLOW_REGISTRY.load(payload)

    plans = build_lesson_fanout_plan(registered)

    lesson_plan = next(plan for plan in plans if plan.branch_key == "lesson_plan")
    assert lesson_plan.entrypoint_node_keys == ("renamed.lesson.entry",)
