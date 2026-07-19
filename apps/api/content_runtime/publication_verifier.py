"""Integrity checks for idempotent replays of published content releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.content_runtime.definition_projection import (
    build_content_json_schema,
    build_content_validation_rules,
)
from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageItemVersion,
    ContentPackageVersion,
    ContentRelease,
    ContentReleaseItem,
    RuntimeDefaultVersion,
)
from apps.api.content_runtime.package_source import (
    BuiltinCoursewareReleaseSource,
    ContentPublicationConflict,
)
from apps.api.content_runtime.registry import DEFAULT_RUNTIME_KEY
from apps.api.workflows.models import WorkflowDefinition, WorkflowDefinitionVersion


@dataclass(frozen=True, slots=True)
class ExistingPublication:
    content_release_id: UUID
    workflow_definition_version_id: UUID
    runtime_default_version_no: int


def verify_existing_publication(
    session: Session,
    source: BuiltinCoursewareReleaseSource,
    package_version: ContentPackageVersion,
) -> ExistingPublication:
    if (
        package_version.status != "published"
        or package_version.checksum != source.package_checksum
        or package_version.manifest_json != source.manifest
        or package_version.runtime_constraint != source.runtime_constraint
    ):
        raise ContentPublicationConflict("package version conflicts with validated source")
    _verify_package_items(session, source, package_version.id)
    _verify_content_definitions(session, source, package_version.id)

    release = session.scalar(
        select(ContentRelease).where(ContentRelease.release_key == source.release_key)
    )
    workflow = session.scalar(
        select(WorkflowDefinitionVersion).where(
            WorkflowDefinitionVersion.checksum == source.workflow_checksum
        )
    )
    if (
        release is None
        or release.status != "published"
        or release.name != f"{source.package_name} {source.semantic_version}"
        or release.notes != source.manifest["change_summary"]
        or workflow is None
        or workflow.status != "published"
        or workflow.graph_json != source.workflow_catalog
        or workflow.input_contract_json != source.workflow_input_contract
    ):
        raise ContentPublicationConflict("published package is missing release or workflow")
    _verify_workflow_identity(session, source, workflow)
    _verify_release_mount(session, release.id, package_version.id)

    default = session.scalar(
        select(RuntimeDefaultVersion).where(
            RuntimeDefaultVersion.runtime_key == DEFAULT_RUNTIME_KEY,
            RuntimeDefaultVersion.content_release_id == release.id,
            RuntimeDefaultVersion.workflow_definition_version_id == workflow.id,
        )
    )
    if default is None:
        raise ContentPublicationConflict("published release is incomplete")
    return ExistingPublication(
        content_release_id=release.id,
        workflow_definition_version_id=workflow.id,
        runtime_default_version_no=default.version_no,
    )


def _verify_package_items(
    session: Session,
    source: BuiltinCoursewareReleaseSource,
    package_version_id: UUID,
) -> None:
    rows = session.scalars(
        select(ContentPackageItemVersion).where(
            ContentPackageItemVersion.content_package_version_id == package_version_id
        )
    )
    items = {row.item_key: row for row in rows}
    if set(items) != set(source.items) or any(
        items[key].payload_json != source.items[key]
        or items[key].checksum != source.manifest_entries[key]["sha256"]
        or items[key].kind != source.manifest_entries[key]["kind"]
        or items[key].schema_id != source.manifest_entries[key]["schema_id"]
        for key in source.items
    ):
        raise ContentPublicationConflict("published package items conflict with source")


def _verify_content_definitions(
    session: Session,
    source: BuiltinCoursewareReleaseSource,
    package_version_id: UUID,
) -> None:
    rows = session.scalars(
        select(ContentDefinitionVersion).where(
            ContentDefinitionVersion.content_package_version_id == package_version_id
        )
    )
    definitions = {row.definition_key: row for row in rows}
    expected_keys = {
        key
        for key, entry in source.manifest_entries.items()
        if entry["kind"] == "content_definition"
    }
    if set(definitions) != expected_keys or any(
        definitions[key].schema_json
        != build_content_json_schema(cast(dict[str, Any], source.items[key]["spec"]))
        or definitions[key].ui_schema_json != {}
        or definitions[key].export_mapping_json != {}
        or definitions[key].validation_rules_json
        != build_content_validation_rules(cast(dict[str, Any], source.items[key]["spec"]))
        or definitions[key].checksum != source.manifest_entries[key]["sha256"]
        for key in expected_keys
    ):
        raise ContentPublicationConflict("content definition projections conflict with source")


def _verify_workflow_identity(
    session: Session,
    source: BuiltinCoursewareReleaseSource,
    workflow: WorkflowDefinitionVersion,
) -> None:
    definition = session.get(WorkflowDefinition, workflow.workflow_definition_id)
    if (
        definition is None
        or definition.workflow_key != source.workflow_key
        or definition.domain != "primary_math"
        or definition.status != "active"
    ):
        raise ContentPublicationConflict("workflow identity conflicts with source")


def _verify_release_mount(
    session: Session,
    release_id: UUID,
    package_version_id: UUID,
) -> None:
    items = list(
        session.scalars(
            select(ContentReleaseItem).where(ContentReleaseItem.content_release_id == release_id)
        )
    )
    if (
        len(items) != 1
        or items[0].content_package_version_id != package_version_id
        or items[0].mount_key != "primary_math"
        or items[0].priority != 100
    ):
        raise ContentPublicationConflict("published release is incomplete")
