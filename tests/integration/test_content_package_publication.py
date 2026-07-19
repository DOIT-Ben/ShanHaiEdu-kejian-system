from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from apps.api.cli import run_publish_golden_content
from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackage,
    ContentPackageItemVersion,
    ContentPackageVersion,
    ContentRelease,
    ContentReleaseItem,
    RuntimeDefaultVersion,
)
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.content_runtime.registry import BUILTIN_RUNTIME_DEFAULTS
from apps.api.content_runtime.service import resolve_runtime_defaults
from apps.api.database import build_engine, build_session_factory
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.workflows.models import WorkflowDefinitionVersion
from tests.fakes.identity import seed_test_actor

ROOT = Path(__file__).resolve().parents[2]


def test_golden_release_is_published_from_validated_fixtures_and_is_idempotent(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        first = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        counts_after_first = publication_counts(session)
        second = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )

        package_version = session.get(ContentPackageVersion, first.content_package_version_id)
        release = session.get(ContentRelease, first.content_release_id)
        workflow = session.get(
            WorkflowDefinitionVersion,
            first.workflow_definition_version_id,
        )
        release_item = session.scalar(
            select(ContentReleaseItem).where(
                ContentReleaseItem.content_release_id == first.content_release_id
            )
        )

        assert first.created is True
        assert second.created is False
        assert second == first.as_existing()
        assert publication_counts(session) == counts_after_first
        assert package_version is not None
        assert package_version.manifest_json == source.manifest
        assert package_version.checksum == source.package_checksum
        assert release is not None and release.status == "published"
        assert release_item is not None
        assert release_item.content_package_version_id == package_version.id
        assert workflow is not None
        assert workflow.graph_json == source.workflow_catalog
        assert workflow.checksum == source.workflow_checksum
        assert session.scalar(
            select(func.count())
            .select_from(ContentPackageItemVersion)
            .where(ContentPackageItemVersion.content_package_version_id == package_version.id)
        ) == len(source.items)
        assert (
            session.scalar(
                select(func.count())
                .select_from(ContentDefinitionVersion)
                .where(ContentDefinitionVersion.content_package_version_id == package_version.id)
            )
            == source.content_definition_count
        )
        assert resolve_runtime_defaults(session).content_release_id == release.id
        assert resolve_runtime_defaults(session).workflow_definition_version_id == workflow.id


def test_publishing_new_default_only_changes_projects_created_after_activation(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        request = CreateProjectRequest(title="Before publish", knowledge_point="One half")
        existing = ProjectRepository(session, actor).create(request)
        published = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        newer = ProjectRepository(session, actor).create(
            request.model_copy(update={"title": "After publish"})
        )

        session.refresh(existing)
        assert existing.content_release_id == BUILTIN_RUNTIME_DEFAULTS.content_release_id
        assert (
            existing.workflow_definition_version_id
            == BUILTIN_RUNTIME_DEFAULTS.workflow_definition_version_id
        )
        assert newer.content_release_id == published.content_release_id
        assert newer.workflow_definition_version_id == published.workflow_definition_version_id


def test_failed_publication_rolls_back_every_new_runtime_row(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)

    with factory() as session, session.begin():
        with pytest.raises(IntegrityError):
            ContentReleasePublisher(session).publish(source, published_by=uuid4())

        assert (
            session.scalar(
                select(func.count())
                .select_from(ContentPackage)
                .where(ContentPackage.package_key == source.package_key)
            )
            == 0
        )
        assert resolve_runtime_defaults(session) == BUILTIN_RUNTIME_DEFAULTS


def test_administrative_cli_publishes_and_replays_without_new_versions(
    migrated_database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_publish_golden_content(database_url=migrated_database_url, root=ROOT) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["conclusion"] == "passed"
    assert first["created"] is True
    assert first["runtime_default_version_no"] == 2

    assert run_publish_golden_content(database_url=migrated_database_url, root=ROOT) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["created"] is False
    assert second["content_release_id"] == first["content_release_id"]


def publication_counts(session) -> tuple[int, ...]:
    models = (
        ContentPackage,
        ContentPackageVersion,
        ContentPackageItemVersion,
        ContentDefinitionVersion,
        ContentRelease,
        ContentReleaseItem,
        WorkflowDefinitionVersion,
        RuntimeDefaultVersion,
    )
    return tuple(session.scalar(select(func.count()).select_from(model)) or 0 for model in models)
