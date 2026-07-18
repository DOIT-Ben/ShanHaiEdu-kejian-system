"""Project exact PPT node outputs from the golden courseware aggregate."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any, cast

PPT_STAGE_NODE_KEYS = (
    "ppt.content_analyze",
    "ppt.outline.generate",
    "ppt.pages.generate",
    "ppt.cover.prompt.generate",
    "ppt.body_asset_prompts.generate",
)

REQUIRED_SOURCE_FIELDS: dict[str, tuple[str, ...]] = {
    "ppt.content_analyze": (
        "ppt.source_lesson_plan_key",
        "ppt.analysis.analysis_key",
        "ppt.analysis.audience_and_use",
        "ppt.analysis.content_boundary",
        "ppt.analysis.must_not_preteach",
        "ppt.analysis.teaching_sequence",
        "ppt.analysis.interaction_points",
        "ppt.analysis.visualization_opportunities",
        "ppt.analysis.must_remain_editable",
        "ppt.analysis.recommended_page_count",
        "ppt.analysis.page_count_recommendation_reason",
        "ppt.analysis.analysis_quality_notes",
    ),
    "ppt.outline.generate": (
        "ppt.outline_key",
        "ppt.source_lesson_plan_key",
        "ppt.outline[*].page_key",
        "ppt.outline[*].position",
        "ppt.outline[*].page_type",
        "ppt.outline[*].teaching_task",
        "ppt.outline[*].source_refs",
        "ppt.outline[*].student_focus",
        "ppt.outline[*].interaction_intent",
        "ppt.outline_coverage_check",
    ),
    "ppt.pages.generate": (
        "ppt.page_spec_set_key",
        "ppt.outline_key",
        "ppt.page_specs[*].page_key",
        "ppt.page_specs[*].position",
        "ppt.page_specs[*].page_type",
        "ppt.page_specs[*].teaching_task",
        "ppt.page_specs[*].source_refs",
        "ppt.page_specs[*].canvas",
        "ppt.page_specs[*].main_visual",
        "ppt.page_specs[*].asset_requirements",
        "ppt.page_specs[*].editable_elements",
        "ppt.page_specs[*].layout",
        "ppt.page_specs[*].interaction",
        "ppt.page_specs[*].speaker_notes",
        "ppt.outline[*].student_focus",
        "ppt.analysis.must_not_preteach",
        "ppt.quality_expectations",
    ),
    "ppt.cover.prompt.generate": (
        "ppt.cover.request_key",
        "ppt.cover.subject",
        "ppt.cover.composition",
        "ppt.cover.material_and_form",
        "ppt.cover.palette_and_lighting",
        "ppt.cover.aspect_ratio",
        "ppt.cover.text_safe_area",
        "ppt.cover.negative_constraints",
        "ppt.cover.candidate_count",
        "ppt.cover.target_slot",
    ),
    "ppt.body_asset_prompts.generate": (
        "ppt.body_package_key",
        "ppt.style_contract.style_key",
        "ppt.page_specs[body].asset_requirements[*].asset_key",
        "ppt.page_specs[body].asset_requirements[*].responsibility",
        "ppt.page_specs[body].asset_requirements[*].target_slot",
        "ppt.page_specs[body].asset_requirements[*].prompt_text",
        "ppt.page_specs[body].asset_requirements[*].negative_constraints",
        "ppt.page_specs[body].canvas.aspect_ratio",
        "ppt.quality_expectations",
    ),
}


def _missing_keys(record: object, prefix: str, keys: tuple[str, ...]) -> list[str]:
    if not isinstance(record, dict):
        return [prefix]
    return [f"{prefix}.{key}" for key in keys if key not in record or record[key] is None]


def _missing_repeated(records: object, prefix: str, keys: tuple[str, ...]) -> list[str]:
    if not isinstance(records, list) or not records:
        return [prefix]
    missing: list[str] = []
    for index, record in enumerate(cast(list[object], records)):
        missing.extend(_missing_keys(record, f"{prefix}[{index}]", keys))
    return missing


def _missing_analysis(ppt: dict[str, Any]) -> list[str]:
    missing = _missing_keys(ppt, "ppt", ("source_lesson_plan_key", "analysis"))
    missing.extend(
        _missing_keys(
            ppt.get("analysis"),
            "ppt.analysis",
            (
                "analysis_key",
                "audience_and_use",
                "content_boundary",
                "must_not_preteach",
                "teaching_sequence",
                "interaction_points",
                "visualization_opportunities",
                "must_remain_editable",
                "recommended_page_count",
                "page_count_recommendation_reason",
                "analysis_quality_notes",
            ),
        )
    )
    return missing


def _missing_outline(ppt: dict[str, Any]) -> list[str]:
    missing = _missing_keys(
        ppt,
        "ppt",
        ("outline_key", "source_lesson_plan_key", "outline", "outline_coverage_check"),
    )
    missing.extend(
        _missing_repeated(
            ppt.get("outline"),
            "ppt.outline",
            (
                "page_key",
                "position",
                "page_type",
                "teaching_task",
                "source_refs",
                "student_focus",
                "interaction_intent",
            ),
        )
    )
    return missing


def _missing_pages(ppt: dict[str, Any]) -> list[str]:
    missing = _missing_keys(
        ppt,
        "ppt",
        (
            "page_spec_set_key",
            "outline_key",
            "page_specs",
            "outline",
            "analysis",
            "quality_expectations",
        ),
    )
    missing.extend(
        _missing_repeated(
            ppt.get("page_specs"),
            "ppt.page_specs",
            (
                "page_key",
                "position",
                "page_type",
                "teaching_task",
                "source_refs",
                "canvas",
                "main_visual",
                "asset_requirements",
                "editable_elements",
                "layout",
                "interaction",
                "speaker_notes",
            ),
        )
    )
    missing.extend(
        _missing_repeated(
            ppt.get("outline"),
            "ppt.outline",
            ("page_key", "student_focus"),
        )
    )
    missing.extend(_missing_keys(ppt.get("analysis"), "ppt.analysis", ("must_not_preteach",)))
    return missing


def _missing_cover(ppt: dict[str, Any]) -> list[str]:
    return _missing_keys(
        ppt.get("cover"),
        "ppt.cover",
        (
            "request_key",
            "subject",
            "composition",
            "material_and_form",
            "palette_and_lighting",
            "aspect_ratio",
            "text_safe_area",
            "negative_constraints",
            "candidate_count",
            "target_slot",
        ),
    )


def _body_pages(ppt: dict[str, Any]) -> list[dict[str, Any]]:
    pages = cast(list[dict[str, Any]], ppt.get("page_specs", []))
    return [page for page in pages if page.get("page_type") != "cover"]


def _missing_body(ppt: dict[str, Any]) -> list[str]:
    missing = _missing_keys(
        ppt,
        "ppt",
        ("body_package_key", "style_contract", "page_specs", "quality_expectations"),
    )
    missing.extend(_missing_keys(ppt.get("style_contract"), "ppt.style_contract", ("style_key",)))
    for page_index, page in enumerate(_body_pages(ppt)):
        page_path = f"ppt.page_specs[body:{page_index}]"
        missing.extend(_missing_keys(page, page_path, ("page_key", "canvas", "asset_requirements")))
        missing.extend(_missing_keys(page.get("canvas"), f"{page_path}.canvas", ("aspect_ratio",)))
        missing.extend(
            _missing_repeated(
                page.get("asset_requirements"),
                f"{page_path}.asset_requirements",
                (
                    "asset_key",
                    "responsibility",
                    "target_slot",
                    "prompt_text",
                    "negative_constraints",
                ),
            )
        )
    if not _body_pages(ppt):
        missing.append("ppt.page_specs[body]")
    return missing


def find_missing_golden_ppt_stage_sources(
    case: dict[str, Any],
) -> dict[str, tuple[str, ...]]:
    """Return exact aggregate paths that prevent each PPT node projection."""

    ppt = case.get("ppt")
    if not isinstance(ppt, dict):
        return {key: ("ppt",) for key in PPT_STAGE_NODE_KEYS}
    ppt_data = cast(dict[str, Any], ppt)
    checks = {
        "ppt.content_analyze": _missing_analysis,
        "ppt.outline.generate": _missing_outline,
        "ppt.pages.generate": _missing_pages,
        "ppt.cover.prompt.generate": _missing_cover,
        "ppt.body_asset_prompts.generate": _missing_body,
    }
    missing: dict[str, tuple[str, ...]] = {}
    for key, check in checks.items():
        paths = check(ppt_data)
        if paths:
            missing[key] = tuple(dict.fromkeys(paths))
    return missing


def _analysis_output(ppt: dict[str, Any]) -> dict[str, Any]:
    source = cast(dict[str, Any], ppt["analysis"])
    return {
        "analysis_key": source["analysis_key"],
        "source_lesson_plan_key": ppt["source_lesson_plan_key"],
        "audience_and_use": source["audience_and_use"],
        "ppt_content_boundary": source["content_boundary"],
        "ppt_must_not_preteach": copy.deepcopy(source["must_not_preteach"]),
        "objective_sequence": copy.deepcopy(source["teaching_sequence"]),
        "interaction_points": copy.deepcopy(source["interaction_points"]),
        "visualization_opportunities": copy.deepcopy(source["visualization_opportunities"]),
        "editable_information_requirements": copy.deepcopy(source["must_remain_editable"]),
        "recommended_page_count": source["recommended_page_count"],
        "page_count_recommendation_reason": source["page_count_recommendation_reason"],
        "analysis_quality_notes": copy.deepcopy(source["analysis_quality_notes"]),
    }


def _outline_page(source: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "outline_page_key": "page_key",
        "outline_position": "position",
        "outline_page_type": "page_type",
        "outline_teaching_task": "teaching_task",
        "outline_source_refs": "source_refs",
        "outline_student_focus": "student_focus",
        "outline_interaction_intent": "interaction_intent",
    }
    return {target: copy.deepcopy(source[origin]) for target, origin in aliases.items()}


def _outline_output(ppt: dict[str, Any]) -> dict[str, Any]:
    coverage = cast(dict[str, Any], ppt["outline_coverage_check"])
    return {
        "outline_key": ppt["outline_key"],
        "outline_source_lesson_plan_key": ppt["source_lesson_plan_key"],
        "outline_pages": [_outline_page(page) for page in ppt["outline"]],
        "outline_coverage_check": copy.deepcopy(coverage),
    }


def _page_validation_rules(ppt: dict[str, Any], source: dict[str, Any]) -> list[str]:
    forbidden = "、".join(cast(list[str], ppt["analysis"]["must_not_preteach"]))
    canvas = cast(dict[str, Any], source["canvas"])
    background_rule = (
        "封面使用cover_art背景" if source["page_type"] == "cover" else "正文使用#FFFFFF纯白背景"
    )
    return [
        "每页只承担一个教学任务",
        background_rule,
        "AI图片不烘焙准确文字、数字、公式或答案",
        "标题、问题、数字、点子、笔顺和匹配关系保持可编辑",
        f"不得提前讲授：{forbidden}",  # noqa: RUF001
        f"画布比例保持{canvas['aspect_ratio']}",
    ]


def _page_output(
    source: dict[str, Any], *, student_focus: str, validation_rules: list[str]
) -> dict[str, Any]:
    visual = cast(dict[str, Any], source["main_visual"])
    editable = cast(list[dict[str, Any]], source["editable_elements"])
    return {
        "page_key": source["page_key"],
        "page_position": source["position"],
        "page_type": source["page_type"],
        "teaching_task": source["teaching_task"],
        "page_source_refs": copy.deepcopy(source["source_refs"]),
        "student_focus": student_focus,
        "canvas": copy.deepcopy(source["canvas"]),
        "visual_decision": visual["visual_decision"],
        "image_strategy": visual["image_strategy"],
        "main_visual_description": visual["description"],
        "page_asset_requirements": copy.deepcopy(source["asset_requirements"]),
        "editable_text_blocks": copy.deepcopy(
            [item for item in editable if item["responsibility"] == "EDITABLE_MATH"]
        ),
        "editable_math_shapes": copy.deepcopy(
            [item for item in editable if item["responsibility"] == "EDITABLE_DIAGRAM"]
        ),
        "layout_spec": copy.deepcopy(source["layout"]),
        "interaction_spec": copy.deepcopy(source["interaction"]),
        "speaker_notes": source["speaker_notes"],
        "page_validation_rules": validation_rules,
    }


def _pages_output(ppt: dict[str, Any]) -> dict[str, Any]:
    student_focus = {item["page_key"]: item["student_focus"] for item in ppt["outline"]}
    return {
        "page_spec_set_key": ppt["page_spec_set_key"],
        "page_spec_outline_key": ppt["outline_key"],
        "page_specs": [
            _page_output(
                page,
                student_focus=student_focus[page["page_key"]],
                validation_rules=_page_validation_rules(ppt, page),
            )
            for page in ppt["page_specs"]
        ],
        "page_set_quality": copy.deepcopy(ppt["quality_expectations"]),
    }


def _cover_output(ppt: dict[str, Any]) -> dict[str, Any]:
    source = cast(dict[str, Any], ppt["cover"])
    aliases = {
        "cover_request_key": "request_key",
        "cover_subject": "subject",
        "cover_composition": "composition",
        "cover_material_and_form": "material_and_form",
        "cover_palette_and_lighting": "palette_and_lighting",
        "cover_aspect_ratio": "aspect_ratio",
        "cover_text_safe_area": "text_safe_area",
        "cover_negative_constraints": "negative_constraints",
        "cover_candidate_count_output": "candidate_count",
        "cover_target_slot": "target_slot",
    }
    return {target: copy.deepcopy(source[origin]) for target, origin in aliases.items()}


def _body_output(ppt: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for page in _body_pages(ppt):
        for requirement in page["asset_requirements"]:
            items.append(
                {
                    "body_item_key": f"BODY-{requirement['asset_key']}",
                    "body_page_key": page["page_key"],
                    "body_requirement_key": requirement["asset_key"],
                    "body_asset_role": requirement["responsibility"],
                    "body_target_slot": requirement["target_slot"],
                    "body_prompt_text": requirement["prompt_text"],
                    "body_negative_constraints": copy.deepcopy(requirement["negative_constraints"]),
                    "body_aspect_ratio": page["canvas"]["aspect_ratio"],
                    "body_consistency_key": ppt["style_contract"]["style_key"],
                }
            )
    return {
        "body_package_key": ppt["body_package_key"],
        "body_style_contract_ref": ppt["style_contract"]["style_key"],
        "body_asset_items": items,
        "body_asset_coverage": {
            "all_body_requirements_covered_once": len(items)
            == sum(len(page["asset_requirements"]) for page in _body_pages(ppt)),
            "target_slots_unique": len({item["body_target_slot"] for item in items}) == len(items),
            "no_placeholder_assets": ppt["quality_expectations"]["no_placeholder_assets"],
        },
    }


def build_golden_ppt_stage_outputs(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build complete PPT outputs, omitting nodes with any missing source fact."""

    ppt = cast(dict[str, Any], case.get("ppt", {}))
    missing = find_missing_golden_ppt_stage_sources(case)
    builders: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "ppt.content_analyze": _analysis_output,
        "ppt.outline.generate": _outline_output,
        "ppt.pages.generate": _pages_output,
        "ppt.cover.prompt.generate": _cover_output,
        "ppt.body_asset_prompts.generate": _body_output,
    }
    return {key: builder(ppt) for key, builder in builders.items() if key not in missing}
