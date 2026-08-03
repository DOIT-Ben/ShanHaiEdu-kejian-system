from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from apps.api.model_gateway.contracts import ModelCapability, TextModelRequest
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.e2e.r1_rescue_node_provider import R1RescueNodeOutputProvider

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


async def test_rescue_provider_returns_the_exact_prompt_lesson_plan() -> None:
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    outputs = build_golden_branch_source_outputs(case)
    original = deepcopy(outputs["lesson_plan.generate"])
    target_evidence_refs = ["EV-MAT-05", "EV-MAT-06", "EV-MAT-07", "EV-MAT-08"]
    unit: dict[str, object] = {
        "lesson_unit_key": "LESSON-RESCUE-002",
        "title": "第二课时隔离验证",
        "duration_minutes": 40,
        "material_scope": "使用同一教材范围验证课时级上下文隔离。",
        "evidence_refs": target_evidence_refs,
        "content_boundary": "只处理第二课时的批准范围。",
        "must_not_preteach": ["不得读取第一课时正文"],
    }
    context = {
        "bindings": [
            {
                "binding_key": "approved_lesson_unit",
                "source": "lesson_division.approved_version",
                "exposure": "full",
                "items": [
                    {
                        "source_id": "division-artifact",
                        "source_version_id": "division-version",
                        "content": {
                            "division_key": "DIVISION-001",
                            "lesson_unit": unit,
                        },
                    }
                ],
            }
        ]
    }
    prompt = (
        "[context:declared_context]\n"
        + json.dumps(context, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + '\n\n[output_schema:request_schema]\n{"lesson_plan_key":{"type":"string"}}'
    )

    result = await R1RescueNodeOutputProvider(outputs).complete(
        TextModelRequest(
            capability=ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH,
            request_id="r1-rescue-second-lesson",
            prompt=prompt,
        )
    )
    content = json.loads(result.text)
    teaching = content["teaching_content"]
    objective_refs = {
        evidence_ref
        for objective in content["teaching_objectives"]
        for evidence_ref in objective["objective_evidence_refs"]
    }

    assert teaching == {
        **original["teaching_content"],
        "lesson_plan_key": "LESSON-PLAN-RESCUE-002",
        "source_lesson_unit_key": unit["lesson_unit_key"],
        "lesson_topic": unit["title"],
        "duration_minutes": unit["duration_minutes"],
        "teaching_scope": unit["material_scope"],
        "teaching_evidence_refs": unit["evidence_refs"],
        "content_boundary": unit["content_boundary"],
        "must_not_preteach": unit["must_not_preteach"],
    }
    assert objective_refs
    assert objective_refs <= set(target_evidence_refs)
    assert objective_refs.isdisjoint(original["teaching_content"]["teaching_evidence_refs"])
    assert outputs["lesson_plan.generate"] == original
