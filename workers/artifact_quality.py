"""Worker composition for queued deterministic artifact quality validation."""

from __future__ import annotations

from uuid import UUID

import dramatiq

from apps.api.artifact_quality.contracts import (
    ArtifactQualityReportResult,
    QualityValidatorRegistry,
)
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.artifact_quality.service import ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import SqlAlchemyArtifactQualityTransactionFactory
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import system_actor
from apps.api.settings import get_settings
from apps.api.workflows.quality_port import QualityNodeRoutingReader

_NON_RETRYABLE_QUALITY_CODES = frozenset(
    {
        "QUALITY_REPORT_BINDING_INVALID",
        "QUALITY_VALIDATOR_UNAVAILABLE",
    }
)
_MAX_RETRIES = 5


def execute_artifact_quality_node(
    database_url: str,
    node_run_id: UUID,
    validators: QualityValidatorRegistry,
) -> ArtifactQualityReportResult | None:
    engine = build_engine(database_url)
    factory = build_session_factory(engine)
    try:
        with factory() as session:
            organization_id = QualityNodeRoutingReader(session).organization_id(node_run_id)
        if organization_id is None:
            return None
        actor = system_actor(organization_id)
        return ArtifactQualityService(
            SqlAlchemyArtifactQualityTransactionFactory(factory, actor),
            validators,
        ).execute(node_run_id)
    finally:
        engine.dispose()


def run_artifact_quality_node(node_run_id: UUID) -> ArtifactQualityReportResult | None:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("worker database persistence is not configured")
    return execute_artifact_quality_node(
        settings.database_url.get_secret_value(),
        node_run_id,
        runtime_quality_validator_registry(),
    )


def _retry_artifact_quality_failure(retries: int, exception: BaseException) -> bool:
    return (
        retries < _MAX_RETRIES
        and getattr(exception, "code", None) not in _NON_RETRYABLE_QUALITY_CODES
    )


@dramatiq.actor(
    max_retries=_MAX_RETRIES,
    min_backoff=1_000,
    max_backoff=30_000,
    retry_when=_retry_artifact_quality_failure,
)
def process_artifact_quality_node(node_run_id: str) -> None:
    run_artifact_quality_node(UUID(node_run_id))
