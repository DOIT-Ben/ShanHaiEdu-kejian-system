"""Published runtime lookup exposed to project creation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.content_runtime.models import ContentRelease, RuntimeDefaultVersion
from apps.api.content_runtime.registry import DEFAULT_RUNTIME_KEY, RuntimeDefaults
from apps.api.workflows.models import WorkflowDefinitionVersion


def resolve_runtime_defaults(
    session: Session,
    *,
    runtime_key: str = DEFAULT_RUNTIME_KEY,
) -> RuntimeDefaults:
    default = session.scalar(
        select(RuntimeDefaultVersion)
        .where(RuntimeDefaultVersion.runtime_key == runtime_key)
        .order_by(RuntimeDefaultVersion.version_no.desc())
        .limit(1)
    )
    if default is None:
        raise RuntimeError("runtime default is not configured")
    return RuntimeDefaults(
        content_release_id=default.content_release_id,
        workflow_definition_version_id=default.workflow_definition_version_id,
    )


def require_published_runtime(session: Session, defaults: RuntimeDefaults) -> None:
    release = session.get(ContentRelease, defaults.content_release_id)
    workflow = session.get(
        WorkflowDefinitionVersion,
        defaults.workflow_definition_version_id,
    )
    if release is None or release.status != "published":
        raise RuntimeError("default content release is not published")
    if workflow is None or workflow.status != "published":
        raise RuntimeError("default workflow definition version is not published")
