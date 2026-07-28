#!/usr/bin/env python3
"""Seed the controlled teacher's two-LessonUnit rescue browser fixture."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.service import ArtifactService
from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
    ReplaceMode,
)
from apps.api.assets.project_service import ProjectAssetService
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.context import ActorContext, AuthenticatedIdentity
from apps.api.identity.models import Principal
from apps.api.identity.repository import IdentityRepository
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonBranchConfig, LessonUnit
from apps.api.workflows.lesson_fanout import LessonWorkflowFanoutService
from apps.api.workflows.lesson_fanout_contracts import LessonFanoutTarget
from apps.api.workflows.models import BranchRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from tests.integration.test_project_asset_bindings import (
    seed_file_version,  # pyright: ignore[reportUnknownVariableType]
)

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"
PROJECT_TITLE = "十二部分教案验收"
ACCEPTANCE_LOCATOR_ENV = "SHANHAI_R1_ACCEPTANCE_LOCATOR"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _build_material_content(case: dict[str, object]) -> dict[str, object]:
    raw_evidence = case.get("material_evidence")
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise RuntimeError("the golden case material evidence is unavailable")

    records: list[tuple[int, str, str, str]] = []
    for raw_item in cast(list[object], raw_evidence):
        if not isinstance(raw_item, dict):
            raise RuntimeError("the golden case material evidence is invalid")
        item = cast(dict[str, object], raw_item)
        page_index = item.get("pdf_page_index")
        evidence_key = item.get("evidence_key")
        locator = item.get("locator")
        supported_claim = item.get("supported_claim")
        if (
            type(page_index) is not int
            or not isinstance(evidence_key, str)
            or not isinstance(locator, str)
            or not isinstance(supported_claim, str)
        ):
            raise RuntimeError("the golden case material evidence is invalid")
        records.append((page_index, evidence_key, locator, supported_claim))

    source_page_indexes = sorted({record[0] for record in records})
    if not source_page_indexes:
        raise RuntimeError("the golden case material evidence has no physical pages")
    page_number_by_index = {
        source_page_index: page_number
        for page_number, source_page_index in enumerate(source_page_indexes, start=1)
    }
    pages = [
        {
            "page_number": page_number_by_index[source_page_index],
            "text_blocks": [
                {
                    "block_id": evidence_key,
                    "text": f"{locator}: {supported_claim}",
                }
                for page_index, evidence_key, locator, supported_claim in records
                if page_index == source_page_index
            ],
            "image_references": [],
        }
        for source_page_index in source_page_indexes
    ]
    return {
        "source": case["source"],
        "knowledge_boundary": case["knowledge_boundary"],
        "pages": pages,
    }


def _write_acceptance_locator(
    *,
    project_id: UUID,
    lesson_unit_id: UUID,
    isolation_lesson_unit_id: UUID,
) -> None:
    configured = os.environ.get(ACCEPTANCE_LOCATOR_ENV)
    if not configured:
        return
    destination = Path(configured)
    if not destination.is_absolute():
        raise RuntimeError(f"{ACCEPTANCE_LOCATOR_ENV} must be an absolute path")
    resolved = destination.resolve()
    if resolved.is_relative_to(ROOT):
        raise RuntimeError("the R1 acceptance locator must remain outside the repository")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(
            {
                "project_id": str(project_id),
                "lesson_unit_id": str(lesson_unit_id),
                "isolation_lesson_unit_id": str(isolation_lesson_unit_id),
            },
            ensure_ascii=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def _enable_video_branch_and_bind_keyframe(
    session: Session,
    actor: ActorContext,
    *,
    project_id: UUID,
    lesson: LessonUnit,
) -> None:
    config = session.scalar(
        select(LessonBranchConfig).where(
            LessonBranchConfig.lesson_unit_id == lesson.id,
            LessonBranchConfig.branch_key == "video",
        )
    )
    branch = session.scalar(
        select(BranchRun).where(
            BranchRun.lesson_unit_id == lesson.id,
            BranchRun.branch_key == "video",
        )
    )
    if config is None or branch is None:
        raise RuntimeError("the rescue video branch was not materialized")
    config.enabled = True
    config.updated_by = actor.principal_id
    branch.status = "active"
    branch.started_at = branch.started_at or utc_now()
    branch.updated_by = actor.principal_id

    version = seed_file_version(session, actor)
    service = ProjectAssetService(session, actor)
    slot = service.declare_slot(
        project_id,
        AssetSlotDeclaration(
            slot_key=f"lesson.{lesson.position:02d}.video.keyframe",
            lesson_unit_id=lesson.id,
            asset_type="image",
            cardinality=AssetCardinality.ONE,
            required=True,
            target_contract=AssetTargetContract(
                allowed_mime_types=("image/png",),
                require_clean_scan=True,
            ),
        ),
        request_id=f"r1-rescue-video-keyframe-slot-{lesson.id}",
    )
    service.bind(
        slot.id,
        file_asset_version_id=version.id,
        source_artifact_version_id=None,
        replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
        position=None,
        request_id=f"r1-rescue-video-keyframe-bind-{lesson.id}",
    )


async def seed() -> None:
    engine = build_engine(_required("SHANHAI_DATABASE_URL"))
    factory = build_session_factory(engine)
    try:
        principal_id = UUID(_required("SHANHAI_SESSION_TEACHER_PRINCIPAL_ID"))
        with factory() as session:
            principal = session.get(Principal, principal_id)
            if principal is None or principal.user_id is None:
                raise RuntimeError("the controlled E2E teacher principal is unavailable")
            actor = IdentityRepository(session).resolve_actor(
                AuthenticatedIdentity(
                    user_id=principal.user_id,
                    organization_id=principal.organization_id,
                )
            )

        case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
        outputs = build_golden_branch_source_outputs(case)
        material_content = _build_material_content(case)
        material_pages = cast(list[object], material_content["pages"])
        prepared = await _prepare_approval(
            factory,
            case,
            outputs["lesson.division.generate"],
            actor=actor,
            material_content=material_content,
            material_scope_page_range=(1, len(material_pages)),
            project_title=PROJECT_TITLE,
        )
        with factory() as session, session.begin():
            ArtifactService(session, actor).review(
                prepared.version_id,
                action="approve",
                comment="Approve the exact division for the R1 rescue browser fixture.",
                request_id="r1-rescue-e2e-approve-division",
            )

        with factory() as session, session.begin():
            first = session.scalar(
                select(LessonUnit).where(
                    LessonUnit.project_id == prepared.project_id,
                    LessonUnit.position == 1,
                )
            )
            if first is None:
                raise RuntimeError("the first rescue LessonUnit was not materialized")
            second = LessonUnit(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                project_id=prepared.project_id,
                lesson_key="LESSON-RESCUE-002",
                position=2,
                title="第二课时隔离验证",
                scope_summary="用于验证两个课时分别生成教案且任务与产物不会串线。",
                objective_summary="独立生成本课时教案, 不读取第一课时教案。",
                estimated_minutes=40,
                source_division_version_id=prepared.version_id,
                status="active",
                created_by=actor.principal_id,
                updated_by=actor.principal_id,
            )
            session.add(second)
            session.flush()
            first_lesson_id = first.id
            isolation_lesson_id = second.id
            branch_enabled: dict[str, bool] = {}
            for branch_key in ("lesson_plan", "intro_options", "ppt", "video"):
                enabled = branch_key == "lesson_plan"
                branch_enabled[branch_key] = enabled
                session.add(
                    LessonBranchConfig(
                        id=new_uuid7(),
                        lesson_unit_id=second.id,
                        branch_key=branch_key,
                        enabled=enabled,
                        settings_json={},
                        created_by=actor.principal_id,
                        updated_by=actor.principal_id,
                    )
                )
            fanout = LessonWorkflowFanoutService(
                session,
                actor,
            ).synchronize_lesson_configuration(
                prepared.project_id,
                LessonFanoutTarget(
                    lesson_unit_id=second.id,
                    branch_enabled=branch_enabled,
                ),
                request_id="r1-rescue-e2e-second-lesson-fanout",
            )
            if fanout is None:
                raise RuntimeError("the rescue workflow run is unavailable for the second lesson")
            _enable_video_branch_and_bind_keyframe(
                session,
                actor,
                project_id=prepared.project_id,
                lesson=first,
            )
        _write_acceptance_locator(
            project_id=prepared.project_id,
            lesson_unit_id=first_lesson_id,
            isolation_lesson_unit_id=isolation_lesson_id,
        )
        print("r1 rescue browser fixture seeded", flush=True)
    finally:
        engine.dispose()


def main() -> int:
    asyncio.run(seed())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
