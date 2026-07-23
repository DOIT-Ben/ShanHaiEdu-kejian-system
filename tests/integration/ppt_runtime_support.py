from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.binding import resolve_quality_report_binding
from apps.api.artifact_quality.contracts import QualityValidationContext, ValidatorOutcome
from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.registry import InMemoryQualityValidatorRegistry
from apps.api.artifact_quality.service import ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import SqlAlchemyArtifactQualityTransactionFactory
from apps.api.artifacts.models import ArtifactVersion
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
    ReplaceMode,
)
from apps.api.assets.project_service import ProjectAssetService
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.database import utc_now
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonUnit
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.ppt_rendering import BackgroundImage
from apps.api.ppt_rendering.images import inspect_background
from apps.api.ppt_runtime.service import PptRuntimeService
from apps.api.ppt_runtime.sqlalchemy import SqlAlchemyPptRuntimeTransactionFactory
from apps.api.workflows.models import BranchRun
from apps.api.workflows.service import WorkflowRuntimeService
from scripts.golden_courseware_ppt_outputs import build_golden_ppt_stage_outputs
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_node_execution_runtime import (
    _seed_approved_artifact,  # pyright: ignore[reportPrivateUsage]
    _seed_runtime,  # pyright: ignore[reportPrivateUsage]
)
from tests.unit.ppt_rendering.helpers import png_bytes
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"
CATALOG_PATH = (
    ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"
)


@dataclass(frozen=True, slots=True)
class PptSeed:
    actor: ActorContext
    project_id: UUID
    workflow_run_id: UUID
    branch_run_id: UUID
    lesson_unit_id: UUID
    page_specs_version_id: UUID
    lesson_plan_version_id: UUID
    background_version_ids: tuple[UUID, ...]
    assemble_node_id: UUID


class PassingValidator:
    def __init__(self, ref: Any) -> None:
        self._ref = ref

    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        return ValidatorOutcome(
            validator=self._ref,
            passed=True,
            findings=(),
            evidence={
                "source_type": context.source_type,
                "source_version_id": str(context.source_version_id),
                "source_content_hash": context.source_content_hash,
            },
        )


def build_ppt_service(
    factory: sessionmaker[Session],
    actor: ActorContext,
    storage: FakeObjectStorage,
) -> PptRuntimeService:
    return PptRuntimeService(
        SqlAlchemyPptRuntimeTransactionFactory(factory, actor),
        storage,
        storage_bucket="shanhaiedu",
    )


def seed_ppt(
    factory: sessionmaker[Session],
    storage: FakeObjectStorage,
    *,
    background_dir: Path | None = None,
) -> PptSeed:
    runtime = _seed_runtime(factory)
    case = cast(dict[str, Any], json.loads(GOLDEN_PATH.read_text(encoding="utf-8")))
    page_output = build_golden_ppt_stage_outputs(case)["ppt.pages.generate"]
    lesson_fact = case["lesson_division"]["lesson_units"][0]
    with factory() as session, session.begin():
        definition = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.definition_key == "ppt.pages.generate.output"
            )
        )
        assert definition is not None
        lesson = LessonUnit(
            id=new_uuid7(),
            organization_id=runtime.actor.organization_id,
            project_id=runtime.project_id,
            lesson_key=lesson_fact["lesson_unit_key"],
            position=lesson_fact["position"],
            title=lesson_fact["title"],
            scope_summary=lesson_fact["material_scope"],
            objective_summary=lesson_fact["core_learning_outcome"],
            estimated_minutes=lesson_fact["duration_minutes"],
            source_division_version_id=runtime.upstream_version_id,
            status="active",
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(lesson)
        session.flush()
        branch = BranchRun(
            id=new_uuid7(),
            workflow_run_id=runtime.workflow_run_id,
            lesson_unit_id=lesson.id,
            branch_key="ppt",
            status="active",
            created_by=runtime.actor.principal_id,
            updated_by=runtime.actor.principal_id,
        )
        session.add(branch)
        session.flush()
        page_specs = _seed_approved_artifact(
            session,
            runtime.actor,
            runtime.project_id,
            definition.id,
            artifact_key=f"ppt-page-specs:{lesson.lesson_key}",
            artifact_type="ppt_page_specs",
            branch_key="ppt",
            lesson_unit_id=lesson.id,
            content=page_output,
        )
        lesson_plan = _seed_approved_artifact(
            session,
            runtime.actor,
            runtime.project_id,
            definition.id,
            artifact_key=f"lesson-plan:{lesson.lesson_key}",
            artifact_type="lesson_plan",
            branch_key="lesson_plan",
            lesson_unit_id=lesson.id,
            content=cast(dict[str, object], case["lesson_plan"]),
        )
        _seed_approved_artifact(
            session,
            runtime.actor,
            runtime.project_id,
            definition.id,
            artifact_key=f"ppt-style:{lesson.lesson_key}",
            artifact_type="ppt_style",
            branch_key="ppt",
            lesson_unit_id=lesson.id,
            content=cast(dict[str, object], case["ppt"]["style_contract"]),
        )

        background_ids: list[UUID] = []
        asset_service = ProjectAssetService(session, runtime.actor)
        for position, page in enumerate(cast(list[dict[str, Any]], case["ppt"]["page_specs"]), 1):
            requirement = page["asset_requirements"][0]
            payload = (
                (background_dir / f"page-{position:02d}.png").read_bytes()
                if background_dir is not None
                else png_bytes(
                    width=160,
                    height=90,
                    red=220 + position,
                    green=240,
                    blue=250,
                )
            )
            image = inspect_background(BackgroundImage(content=payload, media_type="image/png"))
            asset = FileAsset(
                id=new_uuid7(),
                organization_id=runtime.actor.organization_id,
                asset_key=f"golden-ppt-background:{page['page_key']}",
                asset_kind="image",
                current_version_id=None,
                status="active",
                retention_class="project_asset",
                created_by=runtime.actor.principal_id,
                updated_by=runtime.actor.principal_id,
            )
            session.add(asset)
            session.flush()
            key = f"golden/issue-170/{asset.id}/{page['page_key']}.png"
            metadata = storage.put_bytes(
                bucket="shanhaiedu",
                key=key,
                payload=payload,
                media_type="image/png",
            )
            version = FileAssetVersion(
                id=new_uuid7(),
                organization_id=runtime.actor.organization_id,
                file_asset_id=asset.id,
                version_no=1,
                storage_bucket=metadata.bucket,
                storage_key=metadata.key,
                mime_type=metadata.media_type,
                byte_size=metadata.size_bytes,
                sha256=cast(str, metadata.sha256),
                etag=metadata.etag,
                width=image.width,
                height=image.height,
                duration_ms=None,
                page_count=None,
                scan_status="clean",
                metadata_json={"page_key": page["page_key"]},
                derived_from_version_id=None,
                created_at=utc_now(),
                created_by=runtime.actor.principal_id,
            )
            session.add(version)
            session.flush()
            asset.current_version_id = version.id
            slot = asset_service.declare_slot(
                runtime.project_id,
                AssetSlotDeclaration(
                    slot_key=requirement["target_slot"],
                    lesson_unit_id=lesson.id,
                    asset_type="image",
                    cardinality=AssetCardinality.ONE,
                    required=True,
                    target_contract=AssetTargetContract(
                        allowed_mime_types=("image/png",),
                        require_clean_scan=True,
                    ),
                ),
                request_id=f"issue-170-declare-{page['page_key']}",
            )
            asset_service.bind(
                slot.id,
                file_asset_version_id=version.id,
                source_artifact_version_id=page_specs.id,
                replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
                position=None,
                request_id=f"issue-170-bind-{page['page_key']}",
            )
            background_ids.append(version.id)

        assemble = WorkflowRuntimeService(session, runtime.actor).create_branch_node_run(
            runtime.workflow_run_id,
            branch.id,
            node_key="ppt.pages.assemble",
            status=NodeStatus.READY,
        )
    return PptSeed(
        actor=runtime.actor,
        project_id=runtime.project_id,
        workflow_run_id=runtime.workflow_run_id,
        branch_run_id=branch.id,
        lesson_unit_id=lesson.id,
        page_specs_version_id=page_specs.id,
        lesson_plan_version_id=lesson_plan.id,
        background_version_ids=tuple(background_ids),
        assemble_node_id=assemble.id,
    )


def validate_pptx(
    factory: sessionmaker[Session],
    seeded: PptSeed,
    artifact_version_id: UUID,
    file_asset_version_id: UUID,
) -> tuple[UUID, UUID]:
    catalog = cast(dict[str, Any], json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
    binding = resolve_quality_report_binding(
        BUILTIN_WORKFLOW_REGISTRY.load(catalog),
        "ppt.final.validate",
    )
    with factory() as session, session.begin():
        file_version = session.get(FileAssetVersion, file_asset_version_id)
        artifact_version = session.get(ArtifactVersion, artifact_version_id)
        page_specs = session.get(ArtifactVersion, seeded.page_specs_version_id)
        lesson_plan = session.get(ArtifactVersion, seeded.lesson_plan_version_id)
        assert file_version is not None and artifact_version is not None
        assert page_specs is not None and lesson_plan is not None
        file_asset = session.get(FileAsset, file_version.file_asset_id)
        assert file_asset is not None
        workflow = WorkflowRuntimeService(session, seeded.actor)
        node = workflow.create_branch_node_run(
            seeded.workflow_run_id,
            seeded.branch_run_id,
            node_key="ppt.final.validate",
            status=NodeStatus.READY,
        )
        workflow.add_input_snapshot(
            node.id,
            input_key="asset:pptx",
            source_type="asset",
            source_id=file_asset.id,
            source_version_id=file_version.id,
            content_hash=file_version.sha256,
            snapshot={
                "file_asset_version_id": str(file_version.id),
                "mime_type": file_version.mime_type,
                "size_bytes": file_version.byte_size,
                "sha256": file_version.sha256,
                "page_count": file_version.page_count,
                "artifact_version_id": str(artifact_version.id),
            },
        )
        for input_key, version in (
            ("artifact:ppt_page_specs", page_specs),
            ("approval:lesson_plan", lesson_plan),
        ):
            workflow.add_input_snapshot(
                node.id,
                input_key=input_key,
                source_type="artifact",
                source_id=version.artifact_id,
                source_version_id=version.id,
                content_hash=version.content_hash,
                snapshot=dict(version.content_json),
            )
    validators = InMemoryQualityValidatorRegistry(
        {ref: PassingValidator(ref) for ref in binding.validator_refs}
    )
    result = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, seeded.actor),
        validators,
    ).execute(node.id)
    assert result.conclusion == "passed"
    return node.id, result.report_id


def stage_gate(
    factory: sessionmaker[Session],
    seeded: PptSeed,
    artifact_version_id: UUID,
    file_asset_version_id: UUID,
    report_id: UUID,
) -> UUID:
    with factory() as session, session.begin():
        version = session.get(ArtifactVersion, artifact_version_id)
        file_version = session.get(FileAssetVersion, file_asset_version_id)
        report = session.get(ArtifactQualityReport, report_id)
        assert version is not None and file_version is not None and report is not None
        file_asset = session.get(FileAsset, file_version.file_asset_id)
        assert file_asset is not None
        workflow = WorkflowRuntimeService(session, seeded.actor)
        node = workflow.create_branch_node_run(
            seeded.workflow_run_id,
            seeded.branch_run_id,
            node_key="ppt.final.approve",
            status=NodeStatus.READY,
        )
        workflow.add_input_snapshot(
            node.id,
            input_key="asset:pptx",
            source_type="asset",
            source_id=file_asset.id,
            source_version_id=file_version.id,
            content_hash=file_version.sha256,
            snapshot={
                **dict(version.content_json),
                "artifact_version_id": str(version.id),
            },
        )
        workflow.add_input_snapshot(
            node.id,
            input_key="report:ppt_final_quality",
            source_type="quality_report",
            source_id=report.id,
            source_version_id=report.id,
            content_hash=report.evidence_hash,
            snapshot={"conclusion": report.conclusion, "report_id": str(report.id)},
        )
        for target in (
            NodeStatus.QUEUED,
            NodeStatus.RUNNING,
            NodeStatus.REVIEW_REQUIRED,
        ):
            workflow.transition_node(node.id, target)
    return node.id


def count_for_node(
    session: Session,
    model: type[GenerationAttempt] | type[UsageRecord],
    node_run_id: UUID,
) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(model).where(model.node_run_id == node_run_id)
        )
        or 0
    )
