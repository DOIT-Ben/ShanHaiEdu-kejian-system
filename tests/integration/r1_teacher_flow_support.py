from __future__ import annotations

import io
import json
from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"
PDF_PAGE_TEXTS = (
    "Count objects from one to five and match each object to one dot.",
    "Connect quantities, dot cards, and numerals from one to five.",
)


def generated_pdf() -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    for text in PDF_PAGE_TEXTS:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
        )
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(output)
    return output.getvalue()


def two_lesson_division_output(evidence_keys: Sequence[str]) -> dict[str, Any]:
    exact_evidence = list(evidence_keys)
    if len(exact_evidence) < 2:
        raise ValueError("R1 lesson division requires evidence from two physical pages")
    output = deepcopy(_golden_outputs()["lesson.division.generate"])
    source = output["lesson_units"][0]
    midpoint = max(1, len(exact_evidence) // 2)
    evidence_groups = (exact_evidence[:midpoint], exact_evidence[midpoint:])
    if not all(evidence_groups):
        raise ValueError("R1 lesson division requires two non-empty evidence groups")
    units: list[dict[str, Any]] = []
    for position, evidence in enumerate(evidence_groups, start=1):
        unit = deepcopy(source)
        unit["lesson_unit_key"] = f"LESSON-{position:03d}"
        unit["position"] = position
        unit["title"] = f"认识1到5(第{position}课时)"
        unit["material_scope"] = f"真实PDF物理页{position}"
        unit["evidence_refs"] = list(evidence)
        unit["core_learning_outcome"] = f"完成第{position}课时可观察学习结果"
        unit["division_reason"] = f"第{position}页形成独立且连续的40分钟学习任务"
        units.append(unit)
    output["lesson_units"] = units
    output["lesson_count"] = len(units)
    output["scope_summary"] = "真实PDF物理页1至2"
    return output


def lesson_plan_output(unit: dict[str, Any], index: int) -> dict[str, Any]:
    output = deepcopy(_golden_outputs()["lesson_plan.generate"])
    teaching = output["teaching_content"]
    teaching["lesson_plan_key"] = f"LESSON-PLAN-{index:03d}"
    teaching["source_lesson_unit_key"] = unit["lesson_unit_key"]
    teaching["lesson_topic"] = unit["title"]
    teaching["duration_minutes"] = unit["duration_minutes"]
    teaching["teaching_scope"] = unit["material_scope"]
    teaching["teaching_evidence_refs"] = list(unit["evidence_refs"])
    teaching["content_boundary"] = unit["content_boundary"]
    teaching["must_not_preteach"] = list(unit["must_not_preteach"])
    for objective_index, objective in enumerate(output["teaching_objectives"]):
        evidence_index = objective_index % len(unit["evidence_refs"])
        objective["objective_evidence_refs"] = [unit["evidence_refs"][evidence_index]]
    return output


def intro_output(unit: dict[str, Any]) -> dict[str, Any]:
    output = deepcopy(_golden_outputs()["intro.generate_options"])
    output["option_set_key"] = "INTRO-OPTIONS-R1-001"
    output["source_lesson_unit_key"] = unit["lesson_unit_key"]
    output["source_knowledge_point"] = unit["teaching_focus"]
    output["source_material_evidence_keys"] = list(unit["evidence_refs"])
    for option in output["options"]:
        option["lesson_unit_key"] = unit["lesson_unit_key"]
        option["knowledge_point"] = unit["teaching_focus"]
        option["must_not_preteach"] = list(unit["must_not_preteach"])
    return output


def _golden_outputs() -> dict[str, dict[str, Any]]:
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    return build_golden_branch_source_outputs(case)
