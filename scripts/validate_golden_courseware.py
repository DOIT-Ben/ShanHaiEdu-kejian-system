"""Validate the deterministic golden courseware case and optional source PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, NoReturn, cast

from jsonschema import Draft202012Validator, FormatChecker

from scripts.golden_courseware_branch_inputs import (
    BRANCH_START_NODE_KEYS,
    GOLDEN_PLANNING_NODE_KEYS,
    PROVIDER_MEDIA_NODE_KEYS,
    build_golden_branch_source_outputs,
    build_golden_branch_start_inputs,
)
from scripts.golden_courseware_content_validation import (
    validate_content_fields,
    validate_input_fields,
)
from scripts.golden_courseware_downstream_validation import (
    validate_golden_delivery,
    validate_golden_video,
)
from scripts.golden_courseware_stage_inputs import (
    GOLDEN_CHAIN_INPUT_NODE_KEYS,
    MEDIA_BOUNDARY_OUTPUT_ONLY_NODE_KEYS,
    build_golden_chain_inputs,
)
from workflow.content_package import ValidatedContentPackage, validate_content_package

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


def _validate_branch_source_outputs(case: dict[str, Any], package: ValidatedContentPackage) -> None:
    try:
        source_outputs = build_golden_branch_source_outputs(case)
    except (KeyError, StopIteration, TypeError) as exc:
        _fail(
            "GOLDEN_CONTENT_SOURCE_INVALID",
            f"golden aggregate cannot produce branch source output: {exc}",
        )
    if set(source_outputs) != set(GOLDEN_PLANNING_NODE_KEYS):
        missing = sorted(set(GOLDEN_PLANNING_NODE_KEYS) - set(source_outputs))
        unexpected = sorted(set(source_outputs) - set(GOLDEN_PLANNING_NODE_KEYS))
        _fail(
            "GOLDEN_CONTENT_SOURCE_INCOMPLETE",
            f"planning outputs differ; missing={missing}, unexpected={unexpected}",
        )
    for node_key, payload in source_outputs.items():
        generation = cast(dict[str, Any], package.items[node_key]["spec"])
        output_key = cast(str, generation["output_definition_ref"]["item_key"])
        output_spec = cast(dict[str, Any], package.items[output_key]["spec"])
        fields = cast(list[dict[str, Any]], output_spec["fields"])
        validate_content_fields(payload, fields, path=node_key, fail=_fail)


def _validate_node_inputs(
    node_inputs: dict[str, dict[str, Any]], package: ValidatedContentPackage
) -> None:
    for node_key, payload in node_inputs.items():
        generation = cast(dict[str, Any], package.items[node_key]["spec"])
        input_key = cast(str, generation["input_definition_ref"]["item_key"])
        input_spec = cast(dict[str, Any], package.items[input_key]["spec"])
        fields = cast(list[dict[str, Any]], input_spec["fields"])
        validate_input_fields(payload, fields, path=node_key, fail=_fail)


def _validate_branch_start_inputs(case: dict[str, Any], package: ValidatedContentPackage) -> None:
    _validate_branch_source_outputs(case, package)
    branch_inputs = build_golden_branch_start_inputs(case)
    if tuple(branch_inputs) != BRANCH_START_NODE_KEYS:
        _fail("GOLDEN_BRANCH_START_NODE_INVALID", "branch start nodes are incomplete")
    _validate_node_inputs(branch_inputs, package)


def _validate_chain_inputs(case: dict[str, Any], package: ValidatedContentPackage) -> None:
    chain_inputs = build_golden_chain_inputs(case)
    if tuple(chain_inputs) != GOLDEN_CHAIN_INPUT_NODE_KEYS:
        _fail("GOLDEN_CHAIN_INPUT_INCOMPLETE", "planning chain inputs are incomplete")
    if set(chain_inputs) & set(MEDIA_BOUNDARY_OUTPUT_ONLY_NODE_KEYS):
        _fail("GOLDEN_MEDIA_BOUNDARY_INVALID", "media-bound planning nodes need real assets")
    _validate_node_inputs(chain_inputs, package)


def _validate_package_refs(
    case: dict[str, Any],
    *,
    package_root: Path,
    contracts_root: Path,
) -> None:
    package = validate_content_package(package_root, contracts_root=contracts_root)
    entrypoints = set(cast(list[str], package.manifest["entrypoints"]))
    declared = set(cast(list[str], case["generation_templates"]))
    if declared != entrypoints or len(entrypoints) != 22:
        _fail(
            "GOLDEN_TEMPLATE_SET_MISMATCH",
            "golden case must declare exactly the package's 22 generation entrypoints",
        )
    planning = set(GOLDEN_PLANNING_NODE_KEYS)
    provider_media = set(PROVIDER_MEDIA_NODE_KEYS)
    if planning & provider_media or planning | provider_media != entrypoints:
        _fail(
            "GOLDEN_TEMPLATE_SCOPE_MISMATCH",
            "planning and provider-media node scopes must partition all entrypoints",
        )
    _validate_branch_start_inputs(case, package)
    _validate_chain_inputs(case, package)


def _validate_source(case: dict[str, Any]) -> None:
    source = cast(dict[str, Any], case["source"])
    verification = cast(dict[str, Any], source["verification"])
    if not all(
        verification[key]
        for key in ("hash_verified", "page_count_verified", "page_range_visually_verified")
    ):
        _fail("GOLDEN_SOURCE_VERIFICATION_INCOMPLETE", "golden source facts are not verified")
    page_indexes = cast(list[int], source["pdf_page_indexes"])
    printed_pages = cast(list[int], source["printed_pages"])
    mappings = cast(list[dict[str, Any]], source["page_mappings"])
    if [item["pdf_page_index"] for item in mappings] != page_indexes:
        _fail("GOLDEN_SOURCE_PAGE_MAPPING_INVALID", "PDF page mapping order is inconsistent")
    if [item["printed_page"] for item in mappings] != printed_pages:
        _fail("GOLDEN_SOURCE_PAGE_MAPPING_INVALID", "printed page mapping is inconsistent")

    evidence = cast(list[dict[str, Any]], case["material_evidence"])
    _require_unique(
        [item["evidence_key"] for item in evidence],
        code="GOLDEN_EVIDENCE_KEY_DUPLICATE",
        label="material evidence key",
    )
    evidence_keys = {item["evidence_key"] for item in evidence}
    mapping_by_page = {(item["pdf_page_index"], item["printed_page"]): item for item in mappings}
    for mapping in mappings:
        if not set(cast(list[str], mapping["evidence_keys"])).issubset(evidence_keys):
            _fail("GOLDEN_EVIDENCE_REF_INVALID", "page mapping references missing evidence")
    for item in evidence:
        mapping = mapping_by_page.get((item["pdf_page_index"], item["printed_page"]))
        if mapping is None or item["evidence_key"] not in mapping["evidence_keys"]:
            _fail("GOLDEN_EVIDENCE_REF_INVALID", "evidence does not match its page mapping")


def _validate_lesson(case: dict[str, Any]) -> None:
    evidence = cast(list[dict[str, Any]], case["material_evidence"])
    evidence_keys = {item["evidence_key"] for item in evidence}
    division = cast(dict[str, Any], case["lesson_division"])
    units = cast(list[dict[str, Any]], division["lesson_units"])
    if division["lesson_count"] != len(units):
        _fail("GOLDEN_LESSON_COUNT_INVALID", "lesson_count does not match lesson_units")
    if [unit["position"] for unit in units] != list(range(1, len(units) + 1)):
        _fail("GOLDEN_LESSON_POSITION_INVALID", "lesson positions must be contiguous")
    _require_unique(
        [unit["lesson_unit_key"] for unit in units],
        code="GOLDEN_LESSON_KEY_DUPLICATE",
        label="lesson unit key",
    )
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
    unit_keys = {unit["lesson_unit_key"] for unit in units}
    if lesson_plan["source_lesson_unit_key"] not in unit_keys:
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
    lesson_units = cast(list[dict[str, Any]], case["lesson_division"]["lesson_units"])
    target_lesson = next(
        (unit for unit in lesson_units if unit["lesson_unit_key"] == option_set["lesson_unit_key"]),
        None,
    )
    if target_lesson is None:
        _fail("GOLDEN_INTRO_LESSON_SOURCE_INVALID", "intro options reference a missing lesson")
    if option_set["knowledge_point"] != target_lesson["teaching_focus"]:
        _fail("GOLDEN_INTRO_KNOWLEDGE_SOURCE_INVALID", "intro knowledge point differs from lesson")
    counts = Counter(option["primary_tendency"] for option in options)
    generation_mode = cast(str, option_set["generation_mode"])
    if generation_mode == "default_nine":
        if counts != Counter({"science": 3, "application": 3, "story": 3}):
            _fail("GOLDEN_INTRO_TENDENCY_COUNT_INVALID", "primary tendencies must be three each")
        if not any(len(option["secondary_tendencies"]) >= 2 for option in options):
            _fail("GOLDEN_INTRO_TENDENCY_CROSS_MISSING", "golden options need crossed tendencies")
    elif generation_mode == "refine_existing":
        if len(options) != 1:
            _fail("GOLDEN_INTRO_TENDENCY_COUNT_INVALID", "refine_existing must keep one option")
    else:
        _fail("GOLDEN_INTRO_MODE_INVALID", "unsupported intro generation mode")
    _require_unique(
        [option["option_key"] for option in options],
        code="GOLDEN_INTRO_KEY_DUPLICATE",
        label="intro option key",
    )
    scores = [cast(int, option["recommendation_score"]) for option in options]
    if scores.count(max(scores)) != 1:
        _fail("GOLDEN_INTRO_RECOMMENDATION_INVALID", "highest recommendation must be unique")
    forbidden = set(cast(list[str], case["knowledge_boundary"]["must_not_preteach"]))
    for option in options:
        if option["lesson_unit_key"] != target_lesson["lesson_unit_key"]:
            _fail("GOLDEN_INTRO_LESSON_SOURCE_INVALID", "intro option lesson trace differs")
        if option["knowledge_point"] != target_lesson["teaching_focus"]:
            _fail("GOLDEN_INTRO_KNOWLEDGE_SOURCE_INVALID", "intro option knowledge trace differs")
        if option["primary_tendency"] in option["secondary_tendencies"]:
            _fail("GOLDEN_INTRO_TENDENCY_OVERLAP", "primary tendency cannot repeat as secondary")
        if not forbidden.issubset(set(cast(list[str], option["must_not_preteach"]))):
            _fail(
                "GOLDEN_INTRO_KNOWLEDGE_BOUNDARY_INVALID",
                "intro option omits forbidden preteach items",
            )
    selection = cast(dict[str, Any], case["intro_selection"])
    selected = next(
        (option for option in options if option["option_key"] == selection["option_key"]),
        None,
    )
    if selected is None or selected != selection["snapshot"]:
        _fail("GOLDEN_INTRO_SNAPSHOT_INVALID", "selected intro snapshot must be immutable copy")
    recommended = next(
        option for option in options if option["recommendation_score"] == max(scores)
    )
    selection_method = cast(str, selection["selection_method"])
    if selection_method == "policy_default":
        if selection["option_key"] != recommended["option_key"]:
            _fail(
                "GOLDEN_INTRO_SELECTION_INVALID",
                "policy_default must use the unique top recommendation",
            )
    elif selection_method != "teacher_selected":
        _fail("GOLDEN_INTRO_SELECTION_INVALID", "unsupported intro selection method")


def _collect_stable_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for field, child in cast(dict[str, object], value).items():
            if field.endswith("_key") and isinstance(child, str):
                keys.add(child)
            keys.update(_collect_stable_keys(child))
    elif isinstance(value, list):
        for child in cast(list[object], value):
            keys.update(_collect_stable_keys(child))
    return keys


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
    outline = cast(list[dict[str, Any]], ppt["outline"])
    if [page["page_key"] for page in outline] != [page["page_key"] for page in pages]:
        _fail("GOLDEN_PPT_OUTLINE_REF_INVALID", "PPT pages do not match the approved outline")

    plan_key = cast(str, lesson_plan["lesson_plan_key"])
    sections = cast(dict[str, Any], lesson_plan["sections"])
    stable_keys = _collect_stable_keys(sections)
    valid_source_refs = {
        *cast(set[str], {item["evidence_key"] for item in case["material_evidence"]}),
        *stable_keys,
        *(f"{plan_key}.{key}" for key in stable_keys),
        *(f"{plan_key}.{key}" for key in sections),
    }
    for index, page in enumerate(pages):
        source_refs = set(cast(list[str], page["source_refs"]))
        if not source_refs or not source_refs.issubset(valid_source_refs):
            _fail("GOLDEN_PPT_SOURCE_REF_INVALID", "PPT page references a missing source")
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

    _validate_source(case)
    _validate_lesson(case)
    _validate_intro(case)
    _validate_ppt(case)
    validate_golden_video(case, fail=_fail)
    validate_golden_delivery(case, fail=_fail)
    _validate_package_refs(case, package_root=package_root, contracts_root=contracts_root)
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
