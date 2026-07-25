#!/usr/bin/env python3
"""Seed two parsed-material projects for the R1 scope/division browser gate."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import AuthenticatedIdentity
from apps.api.identity.models import Principal
from apps.api.identity.repository import IdentityRepository
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.uploads.models import SourceMaterial
from tests.integration.test_r1_material_scope_api import (
    _seed_material_parse,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)

PRIMARY_PROJECT_TITLE = "教材范围与课时划分验收"
ISOLATION_PROJECT_TITLE = "教材范围隔离验收"
ROOT = Path(__file__).resolve().parents[1]


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def main() -> int:
    engine = build_engine(_required("SHANHAI_DATABASE_URL"))
    factory = build_session_factory(engine)
    try:
        with factory() as session, session.begin():
            principal = session.get(
                Principal,
                UUID(_required("SHANHAI_SESSION_TEACHER_PRINCIPAL_ID")),
            )
            if principal is None or principal.user_id is None:
                raise RuntimeError("the controlled E2E teacher principal is unavailable")
            actor = IdentityRepository(session).resolve_actor(
                AuthenticatedIdentity(
                    user_id=principal.user_id,
                    organization_id=principal.organization_id,
                )
            )
            ContentReleasePublisher(session).publish(
                load_builtin_courseware_release(ROOT),
                published_by=actor.principal_id,
            )
            for title, filename in (
                (PRIMARY_PROJECT_TITLE, "一年级数学教材.pdf"),
                (ISOLATION_PROJECT_TITLE, "隔离项目教材.pdf"),
            ):
                project = ProjectRepository(session, actor).create(
                    CreateProjectRequest(
                        grade="一年级",
                        knowledge_point="1-5的认识",
                        textbook_edition="人教版",
                        title=title,
                    )
                )
                material_id, _ = _seed_material_parse(
                    session,
                    project_id=project.id,
                    organization_id=actor.organization_id,
                    principal_id=actor.principal_id,
                )
                material = session.get(SourceMaterial, material_id)
                if material is None:
                    raise RuntimeError("the parsed E2E material was not persisted")
                material.original_filename = filename
        print("r1 material scope browser fixtures seeded", flush=True)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
