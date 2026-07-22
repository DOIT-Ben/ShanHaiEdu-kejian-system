from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from tests.integration.test_artifact_quality_approval import (
    ApprovalSeed,
    _approval_count,  # pyright: ignore[reportPrivateUsage]
    _execute_report,  # pyright: ignore[reportPrivateUsage]
    _seed_submitted_quality_artifact,  # pyright: ignore[reportPrivateUsage]
)


def test_report_and_new_submit_race_never_applies_old_evidence(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_submitted_quality_artifact(factory)
    barrier = Barrier(2)

    def create_report() -> UUID:
        barrier.wait(timeout=30)
        return _execute_report(factory, seeded, passed=True)

    with ThreadPoolExecutor(max_workers=2) as executor:
        report_future = executor.submit(create_report)
        submit_future = executor.submit(_submit_replacement, factory, seeded, barrier)
        report_id = report_future.result(timeout=60)
        replacement_id = submit_future.result(timeout=60)

    with factory() as session:
        artifact = session.get(Artifact, seeded.artifact_id)
        report = session.get(ArtifactQualityReport, report_id)
        assert artifact is not None and report is not None
        assert artifact.status == "in_review"
        assert artifact.current_submitted_version_id == replacement_id
        assert artifact.current_approved_version_id == seeded.prior_approved_version_id
        assert report.source_artifact_version_id == seeded.version_id
        assert _approval_count(session, replacement_id, "submit") == 1
        assert _approval_count(session, replacement_id, "approve") == 0

    with factory() as session:
        try:
            with session.begin():
                ArtifactService(session, seeded.actor).review(
                    replacement_id,
                    action="approve",
                    comment="Old report cannot unlock the replacement",
                    request_id="req-report-submit-race-approve",
                )
        except ApiError as exc:
            assert exc.code == "ARTIFACT_QUALITY_REQUIRED"
        else:
            raise AssertionError("replacement approval unexpectedly reused an old report")


def test_new_submit_and_approve_race_serializes_on_current_pointer(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_submitted_quality_artifact(factory)
    report_id = _execute_report(factory, seeded, passed=True)
    barrier = Barrier(2)

    def approve() -> tuple[str, UUID | str, dict[str, object]]:
        barrier.wait(timeout=30)
        try:
            with factory() as session, session.begin():
                approval = ArtifactService(session, seeded.actor).review(
                    seeded.version_id,
                    action="approve",
                    comment="Concurrent with a replacement submit",
                    request_id="req-submit-approve-race",
                )
                return "approved", approval.id, dict(approval.quality_evidence_json)
        except ApiError as exc:
            return "rejected", exc.code, {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        submit_future = executor.submit(_submit_replacement, factory, seeded, barrier)
        approve_future = executor.submit(approve)
        replacement_id = submit_future.result(timeout=60)
        approval_result = approve_future.result(timeout=60)

    with factory() as session:
        artifact = session.get(Artifact, seeded.artifact_id)
        assert artifact is not None
        assert artifact.status == "in_review"
        assert artifact.current_submitted_version_id == replacement_id
        assert _approval_count(session, replacement_id, "submit") == 1
        assert _approval_count(session, replacement_id, "approve") == 0
        if approval_result[0] == "approved":
            assert artifact.current_approved_version_id == seeded.version_id
            assert _approval_count(session, seeded.version_id, "approve") == 1
            assert approval_result[2]["report_id"] == str(report_id)
        else:
            assert approval_result[1] == "ARTIFACT_STATE_CONFLICT"
            assert artifact.current_approved_version_id == seeded.prior_approved_version_id
            assert _approval_count(session, seeded.version_id, "approve") == 0
        assert _total_approvals(session, "approve") == 1 + int(approval_result[0] == "approved")


def _submit_replacement(
    factory: sessionmaker[Session],
    seeded: ApprovalSeed,
    barrier: Barrier,
) -> UUID:
    barrier.wait(timeout=30)
    with factory() as session, session.begin():
        repository = ArtifactRepository(session, seeded.actor)
        draft = repository.get_draft(seeded.artifact_id, "main")
        current = session.get(ArtifactVersion, seeded.version_id)
        assert draft is not None and current is not None
        replacement_content = deepcopy(current.content_json)
        teaching_content = replacement_content.get("teaching_content")
        assert isinstance(teaching_content, dict)
        teaching_scope = teaching_content.get("teaching_scope")
        assert isinstance(teaching_scope, str)
        teaching_content["teaching_scope"] = f"{teaching_scope} (concurrent replacement)"
        saved = ArtifactService(session, seeded.actor).save_draft(
            seeded.artifact_id,
            "main",
            expected_lock_version=draft.lock_version,
            content=replacement_content,
            request_id="req-concurrent-replacement-save",
        )
        replacement = ArtifactService(session, seeded.actor).submit(
            seeded.artifact_id,
            "main",
            expected_lock_version=saved.lock_version,
            source_kind="manual",
            request_id="req-concurrent-replacement-submit",
        )
        return replacement.id


def _total_approvals(session: Session, action: str) -> int:
    return int(
        session.scalar(select(func.count()).select_from(Approval).where(Approval.action == action))
        or 0
    )
