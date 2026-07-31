"""Explicit production bootstrap command implementations."""

from __future__ import annotations

import json

from apps.api.database import build_engine, build_session_factory
from apps.api.identity.production_bootstrap import bootstrap_production_identity
from apps.api.settings import get_settings
from apps.api.uploads.storage import bootstrap_object_storage_bucket


def run_bootstrap_production_identity() -> int:
    """Create or verify the first access-code teacher without exposing secrets."""

    settings = get_settings()
    if settings.database_url is None or settings.session_teacher_principal_id is None:
        raise RuntimeError(
            "SHANHAI_DATABASE_URL and SHANHAI_SESSION_TEACHER_PRINCIPAL_ID are required"
        )
    engine = build_engine(settings.database_url.get_secret_value())
    try:
        factory = build_session_factory(engine)
        with factory() as session, session.begin():
            result = bootstrap_production_identity(
                session,
                principal_id=settings.session_teacher_principal_id,
            )
        print(
            json.dumps(
                {
                    "conclusion": "passed",
                    "created": result.created,
                    "organization_id": str(result.organization_id),
                    "user_id": str(result.user_id),
                    "principal_id": str(result.principal_id),
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        engine.dispose()


def run_bootstrap_production_storage() -> int:
    """Create or verify the production bucket as an explicit release step."""

    settings = get_settings()
    created = bootstrap_object_storage_bucket(settings)
    print(
        json.dumps(
            {
                "conclusion": "passed",
                "created": created,
                "bucket": settings.object_storage_bucket,
            },
            ensure_ascii=True,
        )
    )
    return 0
