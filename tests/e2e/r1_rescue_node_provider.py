"""Deterministic lesson-scoped text outputs for the R1 rescue browser flow."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from decimal import Decimal
from typing import cast

from apps.api.model_gateway.contracts import (
    ModelCapability,
    ModelUsage,
    TextModelRequest,
    TextProviderResult,
)
from scripts.golden_courseware_branch_inputs import build_intro_generation_stage_outputs

_CONTEXT_LAYER_PREFIX = "[context:declared_context]\n"
_CONTEXT_LAYER_SUFFIX = "\n\n[output_schema:request_schema]"


class R1RescueNodeOutputProvider:
    provider_name = "r1-rescue-deterministic"
    model_name = "r1-rescue-node-output-v1"

    def __init__(self, outputs: dict[str, dict[str, object]]) -> None:
        self._outputs = outputs
        self._intro_stages = build_intro_generation_stage_outputs(outputs["intro.generate_options"])

    async def complete(self, request: TextModelRequest) -> TextProviderResult:
        if request.capability == ModelCapability.TEXT_STRUCTURED_CREATIVE_EDUCATION:
            output = (
                self._intro_stages[1]
                if "Exact candidate pool JSON:" in request.prompt
                else self._intro_stages[0]
            )
        elif '"lesson_plan_key"' in request.prompt:
            output = _lesson_plan_output_for_prompt(
                self._outputs["lesson_plan.generate"],
                request.prompt,
            )
        elif '"division_key"' in request.prompt:
            output = self._outputs["lesson.division.generate"]
        else:
            raise RuntimeError("the R1 E2E provider received an unsupported output contract")
        return TextProviderResult(
            text=json.dumps(
                output,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ),
            provider_request_id=f"fake:{request.request_id}",
            actual_model=self.model_name,
            finish_reason="stop",
            usage=ModelUsage(
                prompt_tokens=8,
                completion_tokens=4,
                total_tokens=12,
                cost=Decimal("0"),
            ),
        )


def _lesson_plan_output_for_prompt(
    source: Mapping[str, object],
    prompt: str,
) -> dict[str, object]:
    output = deepcopy(dict(source))
    unit = _approved_lesson_unit(prompt)
    teaching = _mapping(output, "teaching_content")
    target_refs = _strings(unit, "evidence_refs")
    source_refs = _strings(teaching, "teaching_evidence_refs")
    if len(source_refs) != len(target_refs):
        raise RuntimeError("the R1 E2E lesson evidence shape changed")
    evidence_mapping = dict(zip(source_refs, target_refs, strict=True))
    lesson_key = _text(unit, "lesson_unit_key")
    if not lesson_key.startswith("LESSON-"):
        raise RuntimeError("the R1 E2E lesson key is invalid")
    teaching.update(
        lesson_plan_key=f"LESSON-PLAN-{lesson_key.removeprefix('LESSON-')}",
        source_lesson_unit_key=lesson_key,
        lesson_topic=_text(unit, "title"),
        duration_minutes=_integer(unit, "duration_minutes"),
        teaching_scope=_text(unit, "material_scope"),
        teaching_evidence_refs=target_refs,
        content_boundary=_text(unit, "content_boundary"),
        must_not_preteach=_strings(unit, "must_not_preteach"),
    )
    raw_objectives = output.get("teaching_objectives")
    if not isinstance(raw_objectives, list) or not raw_objectives:
        raise RuntimeError("the R1 E2E lesson objectives are invalid")
    for raw_objective in cast(list[object], raw_objectives):
        if not isinstance(raw_objective, dict):
            raise RuntimeError("the R1 E2E lesson objectives are invalid")
        objective = cast(dict[str, object], raw_objective)
        refs = _strings(objective, "objective_evidence_refs")
        if any(ref not in evidence_mapping for ref in refs):
            raise RuntimeError("the R1 E2E objective evidence shape changed")
        objective["objective_evidence_refs"] = [evidence_mapping[ref] for ref in refs]
    return output


def _approved_lesson_unit(prompt: str) -> dict[str, object]:
    _prefix, separator, remainder = prompt.partition(_CONTEXT_LAYER_PREFIX)
    if not separator:
        raise RuntimeError("the R1 E2E request has no declared context")
    encoded, separator, _suffix = remainder.partition(_CONTEXT_LAYER_SUFFIX)
    if not separator:
        raise RuntimeError("the R1 E2E request has no output schema layer")
    try:
        decoded = cast(object, json.loads(encoded))
    except json.JSONDecodeError as exc:
        raise RuntimeError("the R1 E2E declared context is invalid") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("the R1 E2E declared context is invalid")
    payload = cast(dict[str, object], decoded)
    raw_bindings = payload.get("bindings")
    if not isinstance(raw_bindings, list):
        raise RuntimeError("the R1 E2E declared context has no bindings")
    bindings: list[dict[str, object]] = []
    for raw_binding in cast(list[object], raw_bindings):
        if not isinstance(raw_binding, dict):
            continue
        binding = cast(dict[str, object], raw_binding)
        if (
            binding.get("binding_key") == "approved_lesson_unit"
            and binding.get("source") == "lesson_division.approved_version"
        ):
            bindings.append(binding)
    if len(bindings) != 1:
        raise RuntimeError("the R1 E2E request has no exact approved lesson")
    raw_items = bindings[0].get("items")
    if not isinstance(raw_items, list):
        raise RuntimeError("the R1 E2E request has no exact approved lesson")
    items = cast(list[object], raw_items)
    if len(items) != 1 or not isinstance(items[0], dict):
        raise RuntimeError("the R1 E2E request has no exact approved lesson")
    content = _mapping(cast(dict[str, object], items[0]), "content")
    return _mapping(content, "lesson_unit")


def _mapping(source: Mapping[str, object], key: str) -> dict[str, object]:
    value = source.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"the R1 E2E {key} value is invalid")
    return cast(dict[str, object], value)


def _text(source: Mapping[str, object], key: str) -> str:
    value = source.get(key)
    if type(value) is not str or not value.strip():
        raise RuntimeError(f"the R1 E2E {key} value is invalid")
    return value


def _integer(source: Mapping[str, object], key: str) -> int:
    value = source.get(key)
    if type(value) is not int or value <= 0:
        raise RuntimeError(f"the R1 E2E {key} value is invalid")
    return value


def _strings(source: Mapping[str, object], key: str) -> list[str]:
    value = source.get(key)
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"the R1 E2E {key} value is invalid")
    items = cast(list[object], value)
    if any(type(item) is not str or not item.strip() for item in items):
        raise RuntimeError(f"the R1 E2E {key} value is invalid")
    strings = cast(list[str], items)
    if len(strings) != len(set(strings)):
        raise RuntimeError(f"the R1 E2E {key} value is invalid")
    return list(strings)
