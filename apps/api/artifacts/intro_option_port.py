"""Artifact-owned facts for the Intro option runtime application service."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifact_quality.contracts import QualitySource
from apps.api.artifacts.lesson_context_projection import project_artifact_context
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.artifacts.quality_gate import ArtifactQualityApprovalGuard
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.assets.quality_port import SqlAlchemyAssetQualitySourcePort
from apps.api.content_runtime.approval_port import ContentDefinitionApprovalReader
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.lessons.approval_port import LessonApprovalReader
from apps.api.prompt_runtime.lesson_context_port import LessonContextSnapshotReader
from apps.api.workflows.artifact_input_selection import ArtifactInputSelectionReader

CONTENT_DEFINITION_KEY = "intro.generate_options.output"
SOURCE_INPUT_REF = "artifact:intro_option_set_source"
ARTIFACT_INPUT_REF = "artifact:intro_option_set"


@dataclass(frozen=True, slots=True)
class ReviewableIntroOptionFact:
    artifact_id: UUID
    artifact_version_id: UUID
    project_id: UUID
    lesson_unit_id: UUID
    lesson_key: str
    content_release_id: UUID
    workflow_definition_version_id: UUID
    lineage_node_run_id: UUID
    lineage_artifact_version_id: UUID
    division: QualitySource
    material: QualitySource
    content_hash: str
    content: dict[str, Any]


class IntroOptionArtifactReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require_exact_source(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
        version_id: UUID,
    ) -> None:
        row = self._session.execute(
            select(ArtifactVersion, Artifact)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                ArtifactVersion.id == version_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                Artifact.organization_id == self._actor.organization_id,
                Artifact.project_id == project_id,
                Artifact.lesson_unit_id == lesson_unit_id,
                Artifact.artifact_type == "intro_option_set",
                Artifact.branch_key == "intro_options",
                Artifact.status == "approved",
                Artifact.current_approved_version_id == ArtifactVersion.id,
                Artifact.deleted_at.is_(None),
            )
            .with_for_update(of=Artifact)
        ).one_or_none()
        if row is None:
            raise _invalid("The exact Intro source is not the current approved version.")

    def require_reviewable(self, artifact_version_id: UUID) -> ReviewableIntroOptionFact:
        record = ArtifactRepository(self._session, self._actor).get_version(artifact_version_id)
        if record is None:
            raise _invalid("The Intro Artifact version is unavailable.", status_code=404)
        version, artifact = record
        project = ProjectAccessService(self._session, self._actor).require(
            artifact.project_id,
            ProjectAction.GENERATE,
        )
        definition_key = ContentDefinitionApprovalReader(self._session).definition_key(
            definition_id=artifact.content_definition_version_id,
            content_release_id=project.content_release_id,
        )
        if (
            definition_key != CONTENT_DEFINITION_KEY
            or artifact.artifact_type != "intro_option_set"
            or artifact.branch_key != "intro_options"
            or artifact.lesson_unit_id is None
            or artifact.status != "in_review"
            or artifact.current_submitted_version_id != version.id
        ):
            raise _invalid("The submitted Artifact is not an exact Intro option set.")
        lesson = LessonApprovalReader(self._session, self._actor).current_lesson(
            project_id=artifact.project_id,
            lesson_unit_id=artifact.lesson_unit_id,
        )
        if lesson is None:
            raise _invalid("The Intro option set is outside an active lesson.")
        lineage = self._generated_lineage(artifact.id, version.version_no)
        self._require_generation_selection(
            cast(UUID, lineage.source_node_run_id),
            version.content_json,
        )
        division, material = self._supporting_inputs(
            context_snapshot_id=cast(UUID, lineage.context_snapshot_id),
            project_id=artifact.project_id,
            lesson_key=lesson.lesson_key,
        )
        return ReviewableIntroOptionFact(
            artifact_id=artifact.id,
            artifact_version_id=version.id,
            project_id=artifact.project_id,
            lesson_unit_id=artifact.lesson_unit_id,
            lesson_key=lesson.lesson_key,
            content_release_id=project.content_release_id,
            workflow_definition_version_id=project.workflow_definition_version_id,
            lineage_node_run_id=cast(UUID, lineage.source_node_run_id),
            lineage_artifact_version_id=lineage.id,
            division=division,
            material=material,
            content_hash=version.content_hash,
            content=dict(version.content_json),
        )

    def require_quality_evidence(self, artifact_version_id: UUID) -> dict[str, str]:
        record = ArtifactRepository(self._session, self._actor).get_version(artifact_version_id)
        if record is None:
            raise _invalid("The Intro Artifact version is unavailable.", status_code=404)
        version, artifact = record
        project = ProjectAccessService(self._session, self._actor).require(
            artifact.project_id,
            ProjectAction.REVIEW,
            for_update=True,
        )
        return ArtifactQualityApprovalGuard(self._session, self._actor).require_evidence(
            artifact,
            version,
            content_release_id=project.content_release_id,
            workflow_definition_version_id=project.workflow_definition_version_id,
        )

    def _generated_lineage(self, artifact_id: UUID, maximum_version_no: int) -> ArtifactVersion:
        version = self._session.scalar(
            select(ArtifactVersion)
            .where(
                ArtifactVersion.artifact_id == artifact_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                ArtifactVersion.version_no <= maximum_version_no,
                ArtifactVersion.source_node_run_id.is_not(None),
                ArtifactVersion.context_snapshot_id.is_not(None),
            )
            .order_by(ArtifactVersion.version_no.desc())
            .limit(1)
        )
        if (
            version is None
            or version.source_node_run_id is None
            or version.context_snapshot_id is None
        ):
            raise _invalid("The Intro option set has no generated fixed-release lineage.")
        return version

    def _require_generation_selection(
        self,
        node_run_id: UUID,
        content: Mapping[str, Any],
    ) -> None:
        try:
            selection = ArtifactInputSelectionReader(
                self._session,
                self._actor,
                error_code="INTRO_OPTION_RUNTIME_INVALID",
            ).for_node(node_run_id)
        except ApiError as exc:
            raise _invalid("The Intro generation source selection is invalid.") from exc
        if selection is None:
            raise _invalid("The Intro generation has no exact source selection.")
        raw_refs = content.get("source_intro_option_version_refs")
        refs = (
            tuple(cast(Sequence[object], raw_refs))
            if isinstance(raw_refs, Sequence) and not isinstance(raw_refs, (str, bytes, bytearray))
            else ()
        )
        mode = content.get("generation_mode")
        if mode == "default_nine" and selection == {} and refs == ():
            return
        selected = selection.get(SOURCE_INPUT_REF)
        if (
            mode == "refine_existing"
            and len(selection) == 1
            and selected is not None
            and refs == (str(selected),)
        ):
            return
        raise _invalid("The Intro output differs from its exact source selection.")

    def _supporting_inputs(
        self,
        *,
        context_snapshot_id: UUID,
        project_id: UUID,
        lesson_key: str,
    ) -> tuple[QualitySource, QualitySource]:
        context = LessonContextSnapshotReader(
            self._session,
            self._actor.organization_id,
        )
        division_version_id = context.artifact_version(
            context_snapshot_id,
            "lesson_division.approved_version",
        )
        division_version, division_artifact = self._approved_artifact_version(
            division_version_id,
            project_id=project_id,
            artifact_type="lesson_division",
        )
        material_identity = context.material_evidence(context_snapshot_id)
        material = SqlAlchemyAssetQualitySourcePort(
            self._session,
            self._actor,
        ).load_supporting(
            project_id,
            contract_ref="content:material_evidence",
            source_id=material_identity.source_material_id,
            source_version_id=material_identity.material_parse_version_id,
        )
        division = QualitySource(
            source_type="artifact",
            source_id=division_artifact.id,
            source_version_id=division_version.id,
            content_hash=division_version.content_hash,
            content=project_artifact_context(
                source="approval:lesson_division",
                lesson_key=lesson_key,
                content=division_version.content_json,
            ),
        )
        return division, material

    def _approved_artifact_version(
        self,
        version_id: UUID,
        *,
        project_id: UUID,
        artifact_type: str,
    ) -> tuple[ArtifactVersion, Artifact]:
        row = self._session.execute(
            select(ArtifactVersion, Artifact)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                ArtifactVersion.id == version_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                Artifact.organization_id == self._actor.organization_id,
                Artifact.project_id == project_id,
                Artifact.artifact_type == artifact_type,
                Artifact.current_approved_version_id == ArtifactVersion.id,
                Artifact.status == "approved",
                Artifact.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            raise _invalid("A frozen Intro supporting Artifact is no longer approved.")
        version, artifact = row
        return version, artifact


def _invalid(message: str, *, status_code: int = 409) -> ApiError:
    return ApiError(status_code=status_code, code="INTRO_OPTION_RUNTIME_INVALID", message=message)
