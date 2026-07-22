"""Build reusable entry inputs for independently developed courseware branches."""

from __future__ import annotations

import copy
from typing import Any, cast

from scripts.golden_courseware_ppt_outputs import build_golden_ppt_stage_outputs
from scripts.golden_courseware_video_outputs import build_golden_video_stage_outputs

BRANCH_START_NODE_KEYS = (
    "lesson_plan.generate",
    "ppt.content_analyze",
    "video.master_script.generate",
)

GOLDEN_PLANNING_NODE_KEYS = (
    "lesson.division.generate",
    "lesson_plan.generate",
    "intro.generate_options",
    "ppt.content_analyze",
    "ppt.outline.generate",
    "ppt.pages.generate",
    "ppt.cover.prompt.generate",
    "ppt.body_asset_prompts.generate",
    "video.master_script.generate",
    "video.rough_storyboard.generate",
    "video.style_master.prompt.generate",
    "video.asset_inventory.generate",
    "video.asset_prompts.generate",
    "video.fine_storyboard.generate",
    "audio.plan.generate",
)

PROVIDER_MEDIA_NODE_KEYS = (
    "ppt.cover.image.generate",
    "ppt.body_assets.generate",
    "video.style_master.image.generate",
    "video.assets.generate",
    "video.shots.generate",
    "audio.tts.generate",
    "video.classroom_quality.evaluate",
)


def _rename(source: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    return {target: copy.deepcopy(source[origin]) for target, origin in aliases.items()}


def _lesson_division_output(case: dict[str, Any]) -> dict[str, Any]:
    division = cast(dict[str, Any], case["lesson_division"])
    lesson_plan = cast(dict[str, Any], case["lesson_plan"])
    analysis = cast(dict[str, Any], lesson_plan["sections"]["material_analysis"])
    units: list[dict[str, Any]] = []
    for source_unit in cast(list[dict[str, Any]], division["lesson_units"]):
        unit = copy.deepcopy(source_unit)
        unit["prior_learning"] = analysis["prior_learning"]
        unit["following_connection"] = analysis["next_learning"]
        units.append(unit)
    coverage = cast(dict[str, Any], division["coverage_assertions"])
    scope_summary = "; ".join(item["scope_summary"] for item in case["source"]["page_mappings"])
    return {
        "division_key": division["division_key"],
        "scope_summary": scope_summary,
        "lesson_count": division["lesson_count"],
        "lesson_units": units,
        "coverage_check": {
            "all_evidence_covered": coverage["all_selected_pages_covered_once"],
            "overlap_free": coverage["overlap_free"],
            "progression_rationale": units[0]["division_reason"],
            "unresolved_questions": [],
        },
    }


def _lesson_plan_process(source: dict[str, Any]) -> dict[str, Any]:
    return _rename(
        source,
        {
            "process_section_key": "section_key",
            "process_type": "process_type",
            "process_title": "title",
            "process_minutes": "minutes",
            "process_objective_keys": "objective_keys",
            "teacher_actions": "teacher_actions",
            "student_actions": "student_actions",
            "key_questions": "key_questions",
            "expected_responses": "expected_responses",
            "process_possible_errors": "possible_errors",
            "scaffolds_and_followups": "scaffolds",
            "process_assessment_evidence": "assessment_evidence",
            "board_updates": "board_updates",
            "process_transition": "transition",
            "process_design_rationale": "design_rationale",
        },
    )


def _lesson_plan_output(case: dict[str, Any]) -> dict[str, Any]:
    lesson = cast(dict[str, Any], case["lesson_plan"])
    sections = cast(dict[str, Any], lesson["sections"])
    project = cast(dict[str, Any], case["project"])
    teaching = cast(dict[str, Any], sections["teaching_content"])
    source_lesson_unit_key = cast(str, lesson["source_lesson_unit_key"])
    approved_lesson = next(
        unit
        for unit in cast(list[dict[str, Any]], case["lesson_division"]["lesson_units"])
        if unit["lesson_unit_key"] == source_lesson_unit_key
    )
    return {
        "teaching_content": {
            "lesson_plan_key": lesson["lesson_plan_key"],
            "source_lesson_unit_key": source_lesson_unit_key,
            "lesson_topic": teaching["topic"],
            "subject": project["subject"],
            "grade": project["grade"],
            "lesson_type": teaching["lesson_type"],
            "duration_minutes": approved_lesson["duration_minutes"],
            "teaching_scope": approved_lesson["material_scope"],
            "teaching_evidence_refs": copy.deepcopy(approved_lesson["evidence_refs"]),
            "content_boundary": approved_lesson["content_boundary"],
            "must_not_preteach": copy.deepcopy(approved_lesson["must_not_preteach"]),
        },
        "material_analysis": copy.deepcopy(sections["material_analysis"]),
        "learner_analysis": _rename(
            sections["learner_analysis"],
            {
                "confirmed_learner_facts": "confirmed_facts",
                "general_learning_characteristics": "general_learning_characteristics",
                "likely_learning_difficulties": "likely_difficulties",
                "likely_misconceptions": "likely_misconceptions",
                "differentiation_needs": "differentiation_needs",
                "learner_unknowns": "unknowns",
            },
        ),
        "design_intent": copy.deepcopy(sections["design_intent"]),
        "teaching_objectives": [
            _rename(
                item,
                {
                    "objective_key": "objective_key",
                    "competency_focus": "competency_focus",
                    "observable_outcome": "observable_outcome",
                    "completion_condition": "condition",
                    "success_criteria": "success_criteria",
                    "objective_evidence_refs": "evidence_refs",
                    "assessment_evidence_keys": "assessment_evidence_keys",
                },
            )
            for item in sections["teaching_objectives"]
        ],
        "key_difficulties_and_strategies": copy.deepcopy(
            sections["key_difficulties_and_strategies"]
        ),
        "preparation": copy.deepcopy(sections["preparation"]),
        "teaching_process": [_lesson_plan_process(item) for item in sections["teaching_process"]],
        "board_design": _rename(
            sections["board_design"],
            {
                "board_layout": "layout",
                "board_final_content": "final_content",
                "board_build_order": "build_order",
            },
        ),
        "lesson_summary": _rename(
            sections["lesson_summary"],
            {
                "summary_questions": "summary_questions",
                "student_summary_evidence": "student_evidence",
                "teacher_closure": "teacher_closure",
            },
        ),
        "differentiated_homework": [
            _rename(
                item,
                {
                    "homework_key": "homework_key",
                    "homework_level": "level",
                    "homework_task": "task",
                    "homework_objective_keys": "objective_keys",
                    "homework_expected_minutes": "expected_minutes",
                    "homework_criteria": "criteria",
                    "homework_answer_guidance": "answer_guidance",
                },
            )
            for item in sections["differentiated_homework"]
        ],
        "teaching_reflection": _rename(
            sections["teaching_reflection"],
            {
                "reflection_state": "state",
                "reflection_prompts": "prompts",
                "teacher_reflection_record": "teacher_record",
            },
        ),
    }


def _intro_generate_options_output(case: dict[str, Any]) -> dict[str, Any]:
    option_set = cast(dict[str, Any], case["intro_option_set"])
    options = copy.deepcopy(cast(list[dict[str, Any]], option_set["options"]))
    recommended = max(
        cast(list[dict[str, Any]], option_set["options"]),
        key=lambda item: cast(int, item["recommendation_score"]),
    )
    target_lesson = next(
        unit
        for unit in cast(list[dict[str, Any]], case["lesson_division"]["lesson_units"])
        if unit["lesson_unit_key"] == option_set["lesson_unit_key"]
    )
    return {
        "option_set_key": option_set["option_set_key"],
        "generation_mode": option_set["generation_mode"],
        "source_intro_option_version_refs": copy.deepcopy(
            option_set["source_intro_option_version_refs"]
        ),
        "source_lesson_unit_key": option_set["lesson_unit_key"],
        "source_knowledge_point": option_set["knowledge_point"],
        "source_material_evidence_keys": copy.deepcopy(target_lesson["evidence_refs"]),
        "options": options,
        "recommendation_summary": {
            "recommended_option_key": recommended["option_key"],
            "single_highest_score": True,
        },
    }


def build_golden_branch_source_outputs(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build exact planning outputs without fabricating provider media facts."""

    outputs = {
        "lesson.division.generate": _lesson_division_output(case),
        "lesson_plan.generate": _lesson_plan_output(case),
        "intro.generate_options": _intro_generate_options_output(case),
    }
    outputs.update(build_golden_ppt_stage_outputs(case))
    outputs.update(build_golden_video_stage_outputs(case))
    return outputs


def _material_snapshot(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": copy.deepcopy(case["source"]),
        "material_evidence": copy.deepcopy(case["material_evidence"]),
        "knowledge_boundary": copy.deepcopy(case["knowledge_boundary"]),
    }


def build_golden_branch_start_inputs(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Project the canonical golden case into three independent branch entry inputs."""

    source_outputs = build_golden_branch_source_outputs(case)
    division = source_outputs["lesson.division.generate"]
    lesson_plan = source_outputs["lesson_plan.generate"]
    units = cast(list[dict[str, Any]], division["lesson_units"])
    source_lesson_unit_key = cast(str, lesson_plan["teaching_content"]["source_lesson_unit_key"])
    lesson_unit = next(unit for unit in units if unit["lesson_unit_key"] == source_lesson_unit_key)
    preferences = cast(dict[str, Any], case["teacher_preferences"])
    project = cast(dict[str, Any], case["project"])
    material = _material_snapshot(case)

    return {
        "lesson_plan.generate": {
            "lesson_unit_ref": copy.deepcopy(lesson_unit),
            "material_evidence_ref": copy.deepcopy(material),
            "lesson_detail_level": preferences["lesson_detail_level"],
            "class_duration_minutes": project["lesson_duration_minutes"],
            "teacher_preferences": copy.deepcopy(preferences),
        },
        "ppt.content_analyze": {
            "presentation_purpose": preferences["presentation_purpose"],
            "aspect_ratio": preferences["ppt_aspect_ratio"],
            "preferred_page_count": preferences["ppt_preferred_page_count"],
            "approved_lesson_plan": copy.deepcopy(lesson_plan),
            "approved_material_evidence": copy.deepcopy(material),
        },
        "video.master_script.generate": {
            "selected_intro_snapshot_ref": copy.deepcopy(case["intro_selection"]["snapshot"]),
            "video_duration_mode": preferences["video_duration_mode"],
            "video_cost_preference": preferences["video_cost_preference"],
            "video_aspect_ratio": preferences["video_aspect_ratio"],
            "video_language": preferences["video_language"],
        },
    }
