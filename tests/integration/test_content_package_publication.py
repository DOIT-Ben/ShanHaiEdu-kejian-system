from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from alembic.config import Config
from jsonschema import Draft202012Validator
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from alembic import command
from apps.api.artifacts.validation import ArtifactValidation
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
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.models import SYSTEM_PRINCIPAL_ID
from apps.api.ids import new_uuid7
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
        definition = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.content_package_version_id == package_version.id,
                ContentDefinitionVersion.definition_key == "lesson.division.generate.output",
            )
        )
        assert definition is not None
        validator = Draft202012Validator(definition.schema_json)
        assert list(validator.iter_errors({}))
        assert list(validator.iter_errors({"unexpected": True}))
        assert definition.schema_json["properties"]["lesson_count"]["minimum"] == 1
        minimum_report = ArtifactValidation.validation_report(
            definition,
            {"lesson_count": 0, "lesson_units": []},
        )
        assert any(error["path"] == ["lesson_count"] for error in minimum_report["errors"])
        count_report = ArtifactValidation.validation_report(
            definition,
            {"lesson_count": 2, "lesson_units": [{}]},
        )
        assert any(
            error["path"] == ["lesson_count"] and "number of items" in error["message"]
            for error in count_report["errors"]
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


def test_published_package_item_cannot_be_moved_to_a_draft_package(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        published = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        published_version = session.get(
            ContentPackageVersion,
            published.content_package_version_id,
        )
        assert published_version is not None
        draft = ContentPackageVersion(
            id=new_uuid7(),
            content_package_id=published_version.content_package_id,
            semantic_version="0.0.0-trigger-test",
            runtime_constraint=source.runtime_constraint,
            manifest_json={},
            archive_asset_version_id=None,
            checksum="0" * 63 + "1",
            status="draft",
            validated_at=utc_now(),
            published_at=None,
        )
        session.add(draft)
        session.flush()
        item = session.scalar(
            select(ContentPackageItemVersion).where(
                ContentPackageItemVersion.content_package_version_id == published_version.id
            )
        )
        assert item is not None
        with pytest.raises(IntegrityError), session.begin_nested():
            item.content_package_version_id = draft.id
            session.flush()


def test_concurrent_first_publication_is_serialized_and_replayed(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)
    lock_acquired = Event()
    allow_first_to_continue = Event()

    class BlockingPublisher(ContentReleasePublisher):
        def _lock_publication(self) -> None:
            super()._lock_publication()
            lock_acquired.set()
            if not allow_first_to_continue.wait(timeout=10):
                raise TimeoutError("test did not release the first publication")

    def publish(*, blocking: bool):
        with factory() as session, session.begin():
            publisher_type = BlockingPublisher if blocking else ContentReleasePublisher
            return publisher_type(session).publish(
                source,
                published_by=SYSTEM_PRINCIPAL_ID,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(publish, blocking=True)
        assert lock_acquired.wait(timeout=5)
        second_future = executor.submit(publish, blocking=False)
        try:
            time.sleep(0.2)
            assert not second_future.done()
        finally:
            allow_first_to_continue.set()
        first = first_future.result(timeout=10)
        second = second_future.result(timeout=10)

    assert first.created is True
    assert second == first.as_existing()


def test_published_content_blocks_destructive_migration_downgrade(
    migrated_database_url: str,
) -> None:
    first = run_publish_cli(migrated_database_url)
    assert first.returncode == 0, first.stderr
    previous = os.environ.get("SHANHAI_DATABASE_URL")
    os.environ["SHANHAI_DATABASE_URL"] = migrated_database_url
    try:
        with pytest.raises(DBAPIError, match="cannot downgrade published content"):
            command.downgrade(Config("alembic.ini"), "f1a6c3e9b205")
    finally:
        if previous is None:
            os.environ.pop("SHANHAI_DATABASE_URL", None)
        else:
            os.environ["SHANHAI_DATABASE_URL"] = previous

    replay = run_publish_cli(migrated_database_url)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)["created"] is False


def test_administrative_cli_publishes_and_replays_without_new_versions(
    migrated_database_url: str,
) -> None:
    first_process = run_publish_cli(migrated_database_url)
    assert first_process.returncode == 0, first_process.stderr
    first = json.loads(first_process.stdout)
    assert first["conclusion"] == "passed"
    assert first["created"] is True
    assert first["runtime_default_version_no"] == 2

    second_process = run_publish_cli(migrated_database_url)
    assert second_process.returncode == 0, second_process.stderr
    second = json.loads(second_process.stdout)
    assert second["created"] is False
    assert second["content_release_id"] == first["content_release_id"]


def run_publish_cli(database_url: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["SHANHAI_DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "apps.api.cli", "publish-golden-content"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


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
