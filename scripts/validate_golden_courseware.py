"""Validate the deterministic golden courseware case and optional source PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, NoReturn, cast

from jsonschema import Draft202012Validator, FormatChecker

from workflow.content_package import validate_content_package

LESSON_SECTION_KEYS = [
    "teaching_content",
    "material_analysis",
    "learner_analysis",
    "design_intent",
    "teaching_objectives",
    "key_difficulties_and_strategies",
    "preparation",
    "teaching_process",
    "board_design",
    "lesson_summary",
    "differentiated_homework",
    "teaching_reflection",
]
FORBIDDEN_VIDEO_SOURCES = {
    "lesson_plan.approved_version",
    "material.approved_parse",
    "ppt_outline.approved_version",
}


class GoldenCoursewareValidationError(ValueError):
    """Stable business validation failure for a golden courseware case."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> NoReturn:
    raise GoldenCoursewareValidationError(code, message)


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        _fail("GOLDEN_JSON_INVALID", f"JSON document must be an object: {path.name}")
    return cast(dict[str, Any], value)


def _require_unique(values: list[object], *, code: str, label: str) -> None:
    serialized = [json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values]
    if len(serialized) != len(set(serialized)):
        _fail(code, f"duplicate {label}")


def _validate_package_refs(
    case: dict[str, Any],
    *,
    package_root: Path,
    contracts_root: Path,
) -> None:
    package = validate_content_package(package_root, contracts_root=contracts_root)
    entrypoints = set(cast(list[str], package.manifest["entrypoints"]))
    declared = set(cast(list[str], case["generation_templates"]))
    if declared != entrypoints or len(entrypoints) != 23:
        _fail(
            "GOLDEN_TEMPLATE_SET_MISMATCH",
            "golden case must declare exactly the package's 23 generation entrypoints",
        )


def _validate_source_and_lesson(case: dict[str, Any]) -> None:
    source = cast(dict[str, Any], case["source"])
    page_indexes = cast(list[int], source["pdf_page_indexes"])
    printed_pages = cast(list[int], source["printed_pages"])
    mappings = cast(list[dict[str, Any]], source["page_mappings"])
    if [item["pdf_page_index"] for item in mappings] != page_indexes:
        _fail("GOLDEN_SOURCE_PAGE_MAPPING_INVALID", "PDF page mapping order is inconsistent")
    if [item["printed_page"] for item in mappings] != printed_pages:
        _fail("GOLDEN_SOURCE_PAGE_MAPPING_INVALID", "printed page mapping is inconsistent")

    evidence = cast(list[dict[str, Any]], case["material_evidence"])
    evidence_keys = {item["evidence_key"] for item in evidence}
    for mapping in mappings:
        if not set(cast(list[str], mapping["evidence_keys"])).issubset(evidence_keys):
            _fail("GOLDEN_EVIDENCE_REF_INVALID", "page mapping references missing evidence")

    division = cast(dict[str, Any], case["lesson_division"])
    units = cast(list[dict[str, Any]], division["lesson_units"])
    if division["lesson_count"] != len(units):
        _fail("GOLDEN_LESSON_COUNT_INVALID", "lesson_count does not match lesson_units")
    if [unit["position"] for unit in units] != list(range(1, len(units) + 1)):
        _fail("GOLDEN_LESSON_POSITION_INVALID", "lesson positions must be contiguous")
    project = cast(dict[str, Any], case["project"])
    expected_duration = project["lesson_duration_minutes"]
    if any(unit["duration_minutes"] != expected_duration for unit in units):
        _fail("GOLDEN_LESSON_DURATION_INVALID", "lesson duration differs from project policy")
    for unit in units:
        if not set(cast(list[str], unit["evidence_refs"])).issubset(evidence_keys):
            _fail("GOLDEN_EVIDENCE_REF_INVALID", "lesson unit references missing evidence")

    boundary = cast(dict[str, Any], case["knowledge_boundary"])
    forbidden = set(cast(list[str], boundary["must_not_preteach"]))
    for unit in units:
        if not forbidden.issubset(set(cast(list[str], unit["must_not_preteach"]))):
            _fail("GOLDEN_KNOWLEDGE_BOUNDARY_INVALID", "lesson omits forbidden preteach items")

    lesson_plan = cast(dict[str, Any], case["lesson_plan"])
    if lesson_plan["source_lesson_unit_key"] != units[0]["lesson_unit_key"]:
        _fail("GOLDEN_LESSON_PLAN_SOURCE_INVALID", "lesson plan source lesson is inconsistent")
    sections = cast(dict[str, Any], lesson_plan["sections"])
    if list(sections) != LESSON_SECTION_KEYS:
        _fail("GOLDEN_LESSON_SECTIONS_INVALID", "lesson plan must use ordered twelve sections")
    process = cast(list[dict[str, Any]], sections["teaching_process"])
    if sum(cast(int, item["minutes"]) for item in process) != expected_duration:
        _fail("GOLDEN_LESSON_PROCESS_DURATION_INVALID", "teaching process duration must close")
    if not any(item.get("process_type") == "learning_start" for item in process):
        _fail("GOLDEN_LESSON_INTRO_MISSING", "lesson body needs an executable learning start")
    if sections["teaching_reflection"].get("state") != "not_taught":
        _fail("GOLDEN_REFLECTION_STATE_INVALID", "pre-class reflection state must be not_taught")


def _validate_intro(case: dict[str, Any]) -> None:
    option_set = cast(dict[str, Any], case["intro_option_set"])
    options = cast(list[dict[str, Any]], option_set["options"])
    counts = Counter(option["category"] for option in options)
    if counts != Counter({"science": 3, "application": 3, "story": 3}):
        _fail("GOLDEN_INTRO_CATEGORY_COUNT_INVALID", "intro categories must be three each")
    _require_unique(
        [option["option_key"] for option in options],
        code="GOLDEN_INTRO_KEY_DUPLICATE",
        label="intro option key",
    )
    scores = [cast(int, option["recommendation_score"]) for option in options]
    if scores.count(max(scores)) != 1:
        _fail("GOLDEN_INTRO_RECOMMENDATION_INVALID", "highest recommendation must be unique")
    selection = cast(dict[str, Any], case["intro_selection"])
    selected = next(
        (option for option in options if option["option_key"] == selection["option_key"]),
        None,
    )
    if selected is None or selected != selection["snapshot"]:
        _fail("GOLDEN_INTRO_SNAPSHOT_INVALID", "selected intro snapshot must be immutable copy")


def _validate_ppt(case: dict[str, Any]) -> None:
    ppt = cast(dict[str, Any], case["ppt"])
    lesson_plan = cast(dict[str, Any], case["lesson_plan"])
    if ppt["source_lesson_plan_key"] != lesson_plan["lesson_plan_key"]:
        _fail("GOLDEN_PPT_SOURCE_INVALID", "PPT must read the approved lesson plan")
    pages = cast(list[dict[str, Any]], ppt["page_specs"])
    if [page["position"] for page in pages] != list(range(1, len(pages) + 1)):
        _fail("GOLDEN_PPT_PAGE_POSITION_INVALID", "PPT page positions must be contiguous")
    _require_unique(
        [page["page_key"] for page in pages],
        code="GOLDEN_PPT_PAGE_KEY_DUPLICATE",
        label="PPT page key",
    )
    for index, page in enumerate(pages):
        canvas = cast(dict[str, Any], page["canvas"])
        if index == 0:
            if page["page_type"] != "cover" or canvas["background_mode"] != "cover_art":
                _fail("GOLDEN_PPT_COVER_INVALID", "first page must be cover_art cover")
        elif (
            canvas.get("background_mode") != "solid_white"
            or canvas.get("background_color") != "#FFFFFF"
        ):
            _fail("GOLDEN_PPT_BODY_BACKGROUND_INVALID", "body pages must be pure white")
        if not cast(list[object], page["asset_requirements"]):
            _fail("GOLDEN_PPT_MAIN_VISUAL_MISSING", "every page needs a visual asset")
        responsibilities = {
            item["responsibility"] for item in cast(list[dict[str, Any]], page["editable_elements"])
        }
        if not responsibilities.issubset({"EDITABLE_MATH", "EDITABLE_DIAGRAM"}):
            _fail("GOLDEN_PPT_EDITABLE_RESPONSIBILITY_INVALID", "editable layer is invalid")
        for asset in cast(list[dict[str, Any]], page["asset_requirements"]):
            if asset["responsibility"] not in {"AI_SCENE", "AI_ASSET"}:
                _fail("GOLDEN_PPT_ASSET_RESPONSIBILITY_INVALID", "AI asset role is invalid")


def _validate_video(case: dict[str, Any]) -> None:
    video = cast(dict[str, Any], case["video"])
    selection = cast(dict[str, Any], case["intro_selection"])
    if video["selected_intro_option_key"] != selection["option_key"]:
        _fail("GOLDEN_VIDEO_SOURCE_INVALID", "video must use the selected intro option")
    policy = cast(dict[str, Any], video["source_policy"])
    if policy["allowed_sources"] != ["intro_selection.snapshot"]:
        _fail("GOLDEN_VIDEO_CONTEXT_INVALID", "video has more than the selected snapshot")
    if not FORBIDDEN_VIDEO_SOURCES.issubset(set(cast(list[str], policy["forbidden_sources"]))):
        _fail("GOLDEN_VIDEO_CONTEXT_INVALID", "video forbidden sources are incomplete")

    snapshot = cast(dict[str, Any], selection["snapshot"])
    master = cast(dict[str, Any], video["master_script"])
    if master["selected_intro_option_key"] != snapshot["option_key"]:
        _fail("GOLDEN_VIDEO_MASTER_SOURCE_INVALID", "master script source is inconsistent")
    handoff = cast(dict[str, Any], master["handoff"])
    for key in ("course_anchor", "classroom_first_question", "handoff_moment"):
        if handoff[key] != snapshot[key]:
            _fail("GOLDEN_VIDEO_HANDOFF_INVALID", f"master script changed {key}")
    if handoff["must_not_preteach"] != snapshot["must_not_preteach"]:
        _fail("GOLDEN_VIDEO_HANDOFF_INVALID", "master script changed must_not_preteach")

    rough = cast(dict[str, Any], video["rough_storyboard"])
    beats = cast(list[dict[str, Any]], rough["beats"])
    target_duration = cast(int, master["target_duration_seconds"])
    if sum(cast(int, beat["duration_seconds"]) for beat in beats) != target_duration:
        _fail("GOLDEN_VIDEO_ROUGH_DURATION_INVALID", "rough storyboard duration differs")

    inventory = cast(dict[str, Any], video["asset_inventory"])
    categories = cast(dict[str, list[str]], inventory["categories"])
    if set(categories) != {"character", "scene", "prop", "creature"}:
        _fail("GOLDEN_VIDEO_ASSET_CATEGORIES_INVALID", "asset categories must be explicit")
    assets = cast(list[dict[str, Any]], inventory["assets"])
    asset_keys = {asset["asset_key"] for asset in assets}
    if set().union(*(set(values) for values in categories.values())) != asset_keys:
        _fail("GOLDEN_VIDEO_ASSET_CATEGORIES_INVALID", "asset category refs are inconsistent")
    if {
        item["asset_key"] for item in cast(list[dict[str, Any]], video["asset_image_prompts"])
    } != asset_keys:
        _fail("GOLDEN_VIDEO_ASSET_PROMPTS_INVALID", "every asset needs one image prompt")

    fine = cast(dict[str, Any], video["fine_storyboard"])
    shots = cast(list[dict[str, Any]], fine["shots"])
    if [shot["position"] for shot in shots] != list(range(1, len(shots) + 1)):
        _fail("GOLDEN_VIDEO_SHOT_POSITION_INVALID", "shot positions must be contiguous")
    _require_unique(
        [shot["shot_key"] for shot in shots],
        code="GOLDEN_VIDEO_SHOT_KEY_DUPLICATE",
        label="shot key",
    )
    if any(shot["duration_seconds"] not in {10, 15} for shot in shots):
        _fail("GOLDEN_VIDEO_SHOT_DURATION_INVALID", "shot duration must be 10 or 15 seconds")
    if sum(cast(int, shot["duration_seconds"]) for shot in shots) != target_duration:
        _fail("GOLDEN_VIDEO_SHOT_DURATION_INVALID", "shot duration sum differs from target")
    for shot in shots:
        usages = cast(list[dict[str, Any]], shot["asset_usages"])
        if not {usage["asset_key"] for usage in usages}.issubset(asset_keys):
            _fail("GOLDEN_VIDEO_SHOT_ASSET_INVALID", "shot references missing asset")
    if any(shot.get("handoff_marker") for shot in shots[:-1]) or not shots[-1].get(
        "handoff_marker"
    ):
        _fail("GOLDEN_VIDEO_HANDOFF_INVALID", "only the final shot may hand off")

    shot_keys = {shot["shot_key"] for shot in shots}
    clip_expectations = cast(list[dict[str, Any]], video["clip_expectations"])
    if {item["shot_key"] for item in clip_expectations} != shot_keys:
        _fail("GOLDEN_VIDEO_CLIP_EXPECTATION_INVALID", "clip expectations must cover shots")
    if not all(item["formal_clip_after_adopt_and_save"] for item in clip_expectations):
        _fail("GOLDEN_VIDEO_CLIP_EXPECTATION_INVALID", "candidate cannot be a formal clip")

    audio = cast(dict[str, Any], video["audio_plan"])
    for track in cast(list[dict[str, Any]], audio["tracks"]):
        shot_key = track.get("shot_key")
        if shot_key is not None and shot_key not in shot_keys:
            _fail("GOLDEN_AUDIO_SHOT_REF_INVALID", "audio track references missing shot")


def _validate_source_pdf(case: dict[str, Any], source_pdf: Path) -> None:
    from pypdf import PdfReader

    source = cast(dict[str, Any], case["source"])
    digest = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    if digest != source["sha256"]:
        _fail("GOLDEN_SOURCE_HASH_MISMATCH", "source PDF SHA-256 does not match")
    page_count = len(PdfReader(str(source_pdf)).pages)
    if page_count != source["pdf_page_count"]:
        _fail("GOLDEN_SOURCE_PAGE_COUNT_MISMATCH", "source PDF page count does not match")
    if max(cast(list[int], source["pdf_page_indexes"])) > page_count:
        _fail("GOLDEN_SOURCE_PAGE_RANGE_INVALID", "golden page range exceeds source PDF")


def validate_golden_case(
    case: dict[str, Any],
    *,
    package_root: Path,
    contracts_root: Path,
    source_pdf: Path | None = None,
) -> None:
    """Validate cross-artifact golden invariants and optional authoritative PDF facts."""

    _validate_package_refs(case, package_root=package_root, contracts_root=contracts_root)
    _validate_source_and_lesson(case)
    _validate_intro(case)
    _validate_ppt(case)
    _validate_video(case)
    if source_pdf is not None:
        _validate_source_pdf(case, source_pdf)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=root / "contracts" / "fixtures" / "primary-math-courseware-package",
    )
    parser.add_argument("--contracts-root", type=Path, default=root / "contracts")
    parser.add_argument("--source-pdf", type=Path)
    args = parser.parse_args()
    case = _load_object(args.case)
    schema = _load_object(args.contracts_root / "golden-courseware-case.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(case)
    validate_golden_case(
        case,
        package_root=args.package_root,
        contracts_root=args.contracts_root,
        source_pdf=args.source_pdf,
    )
    print(f"validated {case['case_key']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
