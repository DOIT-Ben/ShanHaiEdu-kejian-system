"""Validated, atomic publication of built-in content packages."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackage,
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
from apps.api.database import utc_now
from apps.api.ids import new_uuid7
from apps.api.workflows.models import WorkflowDefinition, WorkflowDefinitionVersion


@dataclass(frozen=True, slots=True)
class PublicationResult:
    created: bool
    content_package_version_id: UUID
    content_release_id: UUID
    workflow_definition_version_id: UUID
    runtime_default_version_no: int
    package_checksum: str
    workflow_checksum: str

    def as_existing(self) -> PublicationResult:
        return replace(self, created=False)


class ContentReleasePublisher:
    """Publish one validated package and atomically activate it for new projects."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def publish(
        self,
        source: BuiltinCoursewareReleaseSource,
        *,
        published_by: UUID,
    ) -> PublicationResult:
        with self._session.begin_nested():
            package = self._find_package(source.package_key)
            if package is not None:
                self._require_package_identity(package, source)
                existing = self._find_package_version(package.id, source.semantic_version)
                if existing is not None:
                    return self._require_existing_publication(source, existing)
            else:
                package = self._create_package(source)

            if self._find_release(source.release_key) is not None:
                raise ContentPublicationConflict("release key exists without its package version")
            return self._create_publication(source, package, published_by=published_by)

    def _create_publication(
        self,
        source: BuiltinCoursewareReleaseSource,
        package: ContentPackage,
        *,
        published_by: UUID,
    ) -> PublicationResult:
        published_at = utc_now()
        package_version = self._create_package_version(package.id, source, published_at)
        self._add_package_items(package_version.id, source)
        workflow_version, workflow_created = self._get_or_create_workflow(source)
        release = self._create_release(source, package_version.id, published_by=published_by)

        package_version.status = "published"
        package_version.published_at = published_at
        if workflow_created:
            workflow_version.status = "published"
            workflow_version.published_at = published_at
        release.status = "published"
        release.published_at = published_at
        self._session.flush()

        default_version = RuntimeDefaultVersion(
            id=new_uuid7(),
            runtime_key=DEFAULT_RUNTIME_KEY,
            version_no=self._next_runtime_default_version(),
            content_release_id=release.id,
            workflow_definition_version_id=workflow_version.id,
            activated_at=published_at,
            activated_by=published_by,
        )
        self._session.add(default_version)
        self._session.flush()
        return PublicationResult(
            created=True,
            content_package_version_id=package_version.id,
            content_release_id=release.id,
            workflow_definition_version_id=workflow_version.id,
            runtime_default_version_no=default_version.version_no,
            package_checksum=source.package_checksum,
            workflow_checksum=source.workflow_checksum,
        )

    def _create_package_version(
        self,
        package_id: UUID,
        source: BuiltinCoursewareReleaseSource,
        published_at: datetime,
    ) -> ContentPackageVersion:
        package_version = ContentPackageVersion(
            id=new_uuid7(),
            content_package_id=package_id,
            semantic_version=source.semantic_version,
            runtime_constraint=source.runtime_constraint,
            manifest_json=source.manifest,
            archive_asset_version_id=None,
            checksum=source.package_checksum,
            status="draft",
            validated_at=published_at,
            published_at=None,
        )
        self._session.add(package_version)
        self._session.flush()
        return package_version

    def _create_release(
        self,
        source: BuiltinCoursewareReleaseSource,
        package_version_id: UUID,
        *,
        published_by: UUID,
    ) -> ContentRelease:
        release = ContentRelease(
            id=new_uuid7(),
            release_key=source.release_key,
            name=f"{source.package_name} {source.semantic_version}",
            status="draft",
            published_at=None,
            published_by=published_by,
            notes=cast(str, source.manifest["change_summary"]),
        )
        self._session.add(release)
        self._session.flush()
        self._session.add(
            ContentReleaseItem(
                id=new_uuid7(),
                content_release_id=release.id,
                content_package_version_id=package_version_id,
                mount_key="primary_math",
                priority=100,
            )
        )
        self._session.flush()
        return release

    def _find_package(self, package_key: str) -> ContentPackage | None:
        return self._session.scalar(
            select(ContentPackage)
            .where(ContentPackage.package_key == package_key)
            .with_for_update()
        )

    def _find_package_version(
        self,
        package_id: UUID,
        semantic_version: str,
    ) -> ContentPackageVersion | None:
        return self._session.scalar(
            select(ContentPackageVersion).where(
                ContentPackageVersion.content_package_id == package_id,
                ContentPackageVersion.semantic_version == semantic_version,
            )
        )

    def _find_release(self, release_key: str) -> ContentRelease | None:
        return self._session.scalar(
            select(ContentRelease).where(ContentRelease.release_key == release_key)
        )

    def _create_package(self, source: BuiltinCoursewareReleaseSource) -> ContentPackage:
        package = ContentPackage(
            id=new_uuid7(),
            package_key=source.package_key,
            name=source.package_name,
            package_type="builtin",
            owner_scope="platform",
            status="active",
        )
        self._session.add(package)
        self._session.flush()
        return package

    @staticmethod
    def _require_package_identity(
        package: ContentPackage,
        source: BuiltinCoursewareReleaseSource,
    ) -> None:
        if (
            package.name != source.package_name
            or package.package_type != "builtin"
            or package.owner_scope != "platform"
            or package.status != "active"
        ):
            raise ContentPublicationConflict("content package identity conflicts with source")

    def _add_package_items(
        self,
        package_version_id: UUID,
        source: BuiltinCoursewareReleaseSource,
    ) -> None:
        for item_key, item in source.items.items():
            entry = source.manifest_entries[item_key]
            self._session.add(
                ContentPackageItemVersion(
                    id=new_uuid7(),
                    content_package_version_id=package_version_id,
                    item_key=item_key,
                    kind=cast(str, entry["kind"]),
                    schema_id=cast(str, entry["schema_id"]),
                    payload_json=item,
                    checksum=cast(str, entry["sha256"]),
                )
            )
            if entry["kind"] == "content_definition":
                self._session.add(
                    ContentDefinitionVersion(
                        id=new_uuid7(),
                        definition_key=item_key,
                        content_package_version_id=package_version_id,
                        schema_json=cast(dict[str, Any], item["spec"]),
                        ui_schema_json={},
                        export_mapping_json={},
                        validation_rules_json={},
                        checksum=cast(str, entry["sha256"]),
                    )
                )
        self._session.flush()

    def _get_or_create_workflow(
        self,
        source: BuiltinCoursewareReleaseSource,
    ) -> tuple[WorkflowDefinitionVersion, bool]:
        workflow = self._get_or_create_workflow_definition(source)
        existing = self._session.scalar(
            select(WorkflowDefinitionVersion).where(
                WorkflowDefinitionVersion.checksum == source.workflow_checksum
            )
        )
        if existing is not None:
            if (
                existing.workflow_definition_id != workflow.id
                or existing.status != "published"
                or existing.graph_json != source.workflow_catalog
            ):
                raise ContentPublicationConflict("workflow checksum identifies different content")
            return existing, False
        return self._create_workflow_version(workflow.id, source), True

    def _get_or_create_workflow_definition(
        self,
        source: BuiltinCoursewareReleaseSource,
    ) -> WorkflowDefinition:
        workflow = self._session.scalar(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.workflow_key == source.workflow_key)
            .with_for_update()
        )
        if workflow is None:
            workflow = WorkflowDefinition(
                id=new_uuid7(),
                workflow_key=source.workflow_key,
                name="小学数学标准课件工作流",
                domain="primary_math",
                status="active",
            )
            self._session.add(workflow)
            self._session.flush()
        elif workflow.status != "active" or workflow.domain != "primary_math":
            raise ContentPublicationConflict("workflow identity conflicts with source")
        return workflow

    def _create_workflow_version(
        self,
        workflow_id: UUID,
        source: BuiltinCoursewareReleaseSource,
    ) -> WorkflowDefinitionVersion:
        version_no = (
            self._session.scalar(
                select(func.max(WorkflowDefinitionVersion.version_no)).where(
                    WorkflowDefinitionVersion.workflow_definition_id == workflow_id
                )
            )
            or 0
        ) + 1
        version = WorkflowDefinitionVersion(
            id=new_uuid7(),
            workflow_definition_id=workflow_id,
            version_no=version_no,
            graph_json=source.workflow_catalog,
            input_contract_json={
                "package_key": source.package_key,
                "package_semantic_version": source.semantic_version,
                "package_checksum": source.package_checksum,
                "workflow_checksum": source.workflow_checksum,
            },
            status="draft",
            checksum=source.workflow_checksum,
            published_at=None,
        )
        self._session.add(version)
        self._session.flush()
        return version

    def _next_runtime_default_version(self) -> int:
        current = self._session.scalar(
            select(func.max(RuntimeDefaultVersion.version_no)).where(
                RuntimeDefaultVersion.runtime_key == DEFAULT_RUNTIME_KEY
            )
        )
        return (current or 0) + 1

    def _require_existing_publication(
        self,
        source: BuiltinCoursewareReleaseSource,
        package_version: ContentPackageVersion,
    ) -> PublicationResult:
        if (
            package_version.status != "published"
            or package_version.checksum != source.package_checksum
            or package_version.manifest_json != source.manifest
        ):
            raise ContentPublicationConflict("package version conflicts with validated source")
        item_rows = list(
            self._session.scalars(
                select(ContentPackageItemVersion).where(
                    ContentPackageItemVersion.content_package_version_id == package_version.id
                )
            )
        )
        items = {row.item_key: row for row in item_rows}
        if set(items) != set(source.items) or any(
            items[key].payload_json != source.items[key]
            or items[key].checksum != source.manifest_entries[key]["sha256"]
            for key in source.items
        ):
            raise ContentPublicationConflict("published package items conflict with source")
        release = self._find_release(source.release_key)
        workflow = self._session.scalar(
            select(WorkflowDefinitionVersion).where(
                WorkflowDefinitionVersion.checksum == source.workflow_checksum
            )
        )
        if release is None or release.status != "published" or workflow is None:
            raise ContentPublicationConflict("published package is missing release or workflow")
        release_item = self._session.scalar(
            select(ContentReleaseItem).where(
                ContentReleaseItem.content_release_id == release.id,
                ContentReleaseItem.content_package_version_id == package_version.id,
            )
        )
        default = self._session.scalar(
            select(RuntimeDefaultVersion).where(
                RuntimeDefaultVersion.runtime_key == DEFAULT_RUNTIME_KEY,
                RuntimeDefaultVersion.content_release_id == release.id,
                RuntimeDefaultVersion.workflow_definition_version_id == workflow.id,
            )
        )
        if release_item is None or default is None:
            raise ContentPublicationConflict("published release is incomplete")
        return PublicationResult(
            created=False,
            content_package_version_id=package_version.id,
            content_release_id=release.id,
            workflow_definition_version_id=workflow.id,
            runtime_default_version_no=default.version_no,
            package_checksum=source.package_checksum,
            workflow_checksum=source.workflow_checksum,
        )
