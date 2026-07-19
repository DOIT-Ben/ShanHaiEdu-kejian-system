"""Explicitly register every ORM model for standalone application processes."""

from __future__ import annotations


def register_models() -> None:
    """Load all model modules so SQLAlchemy can resolve cross-module foreign keys."""

    from apps.api.artifacts import models as artifact_models
    from apps.api.assets import models as asset_models
    from apps.api.assets import project_models as project_asset_models
    from apps.api.content_runtime import models as content_runtime_models
    from apps.api.creation import models as creation_models
    from apps.api.identity import models as identity_models
    from apps.api.jobs import models as job_models
    from apps.api.lessons import models as lesson_models
    from apps.api.model_gateway import audit_models as model_gateway_audit_models
    from apps.api.projects import models as project_models
    from apps.api.prompt_runtime import models as prompt_runtime_models
    from apps.api.reliability import models as reliability_models
    from apps.api.uploads import models as upload_models
    from apps.api.workflows import models as workflow_models

    _ = (
        artifact_models,
        asset_models,
        project_asset_models,
        content_runtime_models,
        creation_models,
        identity_models,
        job_models,
        lesson_models,
        model_gateway_audit_models,
        project_models,
        prompt_runtime_models,
        reliability_models,
        upload_models,
        workflow_models,
    )
