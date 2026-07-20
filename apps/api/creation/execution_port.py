"""Creation-package adapter for atomic runtime publication."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.creation.models import CreationPackage, CreationPackageItem
from apps.api.database import utc_now
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.runtime_boundary.contract_values import plain_json_value
from apps.api.runtime_boundary.ports import (
    CreationPackageItemSpec,
    CreationPackageSpec,
    CreationPackageWriteResult,
)


class CreationExecutionPortError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SqlAlchemyCreationPackagePort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def publish(self, spec: CreationPackageSpec) -> CreationPackageWriteResult:
        ProjectAccessService(self._session, self._actor).require(
            spec.project_id,
            ProjectAction.GENERATE,
            for_update=True,
        )
        content_hash = _package_hash(spec)
        existing = self._find_existing(spec.package_key)
        if existing is not None:
            self._require_existing_matches(existing, spec, content_hash)
            return CreationPackageWriteResult(
                creation_package_id=existing.id,
                status=existing.status,
                content_hash=existing.content_hash,
            )
        package = self._new_package(spec, content_hash)
        self._add_items(package.id, spec.items)
        return CreationPackageWriteResult(
            creation_package_id=package.id,
            status=package.status,
            content_hash=package.content_hash,
        )

    def _find_existing(self, package_key: str) -> CreationPackage | None:
        return self._session.scalar(
            select(CreationPackage)
            .where(CreationPackage.package_key == package_key)
            .with_for_update()
        )

    def _require_existing_matches(
        self,
        existing: CreationPackage,
        spec: CreationPackageSpec,
        content_hash: str,
    ) -> None:
        if (
            existing.organization_id != self._actor.organization_id
            or existing.source_project_id != spec.project_id
            or existing.source_workflow_run_id != spec.workflow_run_id
            or existing.source_node_run_id != spec.node_run_id
            or existing.source_artifact_version_id != spec.artifact_version_id
            or existing.lesson_unit_id != spec.lesson_unit_id
            or existing.context_snapshot_id != spec.context_snapshot_id
            or existing.source_prompt_snapshot_id != spec.prompt_snapshot_id
            or existing.content_hash != content_hash
        ):
            raise CreationExecutionPortError(
                "NODE_EXECUTION_PACKAGE_IDEMPOTENCY_CONFLICT",
                "the package key is already bound to different immutable facts",
            )

    def _new_package(
        self,
        spec: CreationPackageSpec,
        content_hash: str,
    ) -> CreationPackage:
        package = CreationPackage(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            package_key=spec.package_key,
            source_project_id=spec.project_id,
            source_workflow_run_id=spec.workflow_run_id,
            source_node_run_id=spec.node_run_id,
            source_artifact_version_id=spec.artifact_version_id,
            lesson_unit_id=spec.lesson_unit_id,
            context_snapshot_id=spec.context_snapshot_id,
            source_prompt_snapshot_id=spec.prompt_snapshot_id,
            package_type=spec.package_type,
            status="ready",
            target_rules_json=cast(dict[str, Any], plain_json_value(spec.target_rules)),
            content_hash=content_hash,
            source_stale_at=None,
            created_at=utc_now(),
            created_by=self._actor.principal_id,
        )
        self._session.add(package)
        self._session.flush()
        return package

    def _add_items(
        self,
        package_id: UUID,
        items: tuple[CreationPackageItemSpec, ...],
    ) -> None:
        for item in items:
            self._session.add(
                CreationPackageItem(
                    id=new_uuid7(),
                    creation_package_id=package_id,
                    item_key=item.item_key,
                    position=item.position,
                    title=item.title,
                    business_prompt=item.business_prompt,
                    prompt_json=cast(dict[str, Any], plain_json_value(item.prompt)),
                    reference_asset_version_ids=[
                        str(asset.asset_version_id) for asset in item.reference_assets
                    ],
                    reference_assets_json=[
                        {"asset_version_id": str(asset.asset_version_id), "role": asset.role}
                        for asset in item.reference_assets
                    ],
                    output_spec_json=cast(dict[str, Any], plain_json_value(item.output_spec)),
                    target_slot_key=item.target_slot_key,
                    consistency_key=item.consistency_key,
                    content_hash=_item_hash(item),
                )
            )
        self._session.flush()

    def find_for_node(self, node_run_id: UUID) -> UUID | None:
        return self._session.scalar(
            select(CreationPackage.id).where(
                CreationPackage.organization_id == self._actor.organization_id,
                CreationPackage.source_node_run_id == node_run_id,
            )
        )


def _package_hash(spec: CreationPackageSpec) -> str:
    payload = {
        "package_key": spec.package_key,
        "package_type": spec.package_type,
        "project_id": str(spec.project_id),
        "workflow_run_id": str(spec.workflow_run_id),
        "node_run_id": str(spec.node_run_id),
        "lesson_unit_id": str(spec.lesson_unit_id) if spec.lesson_unit_id else None,
        "artifact_version_id": str(spec.artifact_version_id),
        "context_snapshot_id": str(spec.context_snapshot_id),
        "prompt_snapshot_id": str(spec.prompt_snapshot_id),
        "target_rules": spec.target_rules,
        "items": [_item_payload(item) for item in spec.items],
    }
    return canonical_content_hash(cast(Mapping[str, Any], payload))


def _item_hash(item: CreationPackageItemSpec) -> str:
    return canonical_content_hash(cast(Mapping[str, Any], _item_payload(item)))


def _item_payload(item: CreationPackageItemSpec) -> dict[str, Any]:
    return {
        "item_key": item.item_key,
        "position": item.position,
        "title": item.title,
        "business_prompt": item.business_prompt,
        "prompt": item.prompt,
        "reference_assets": [
            {"asset_version_id": str(asset.asset_version_id), "role": asset.role}
            for asset in item.reference_assets
        ],
        "output_spec": item.output_spec,
        "target_slot_key": item.target_slot_key,
        "consistency_key": item.consistency_key,
    }
