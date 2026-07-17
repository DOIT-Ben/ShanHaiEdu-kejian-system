"""Published runtime lookup exposed to project creation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.content_runtime.models import ContentRelease
from apps.api.content_runtime.registry import RuntimeDefaults
from apps.api.workflows.models import WorkflowDefinitionVersion


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
