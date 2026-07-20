"""Asset-owned context adapter for generic node execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.project_models import ProjectAssetSlot
from apps.api.assets.repository import FileAssetRepository
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.runtime_boundary.ports import (
    AssetContextItem,
    ReferenceAssetAuthorization,
    RuntimeNodeDefinition,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)


class AssetExecutionPortError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SqlAlchemyAssetPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = FileAssetRepository(session, actor)

    def list_context_items(
        self,
        project_id: UUID,
        source: str,
    ) -> tuple[AssetContextItem, ...]:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.GENERATE,
        )
        if source == "material.approved_parse":
            rows = self._repository.list_succeeded_parses_for_project(project_id)
            return tuple(
                AssetContextItem(
                    source_id=parse.source_material_id,
                    source_version_id=parse.id,
                    media_type="application/json",
                    content_hash=parse.text_checksum or _hash_json(parse.content_json or {}),
                    facts=cast(Mapping[str, Any], parse.content_json or {}),
                )
                for parse in rows
            )
        if source.startswith("file_asset:"):
            asset_kind = source.removeprefix("file_asset:")
            rows = self._session.execute(
                select(FileAsset, FileAssetVersion)
                .join(FileAssetVersion, FileAssetVersion.id == FileAsset.current_version_id)
                .where(
                    FileAsset.organization_id == self._actor.organization_id,
                    FileAsset.deleted_at.is_(None),
                    FileAsset.asset_kind == asset_kind,
                    FileAsset.status == "active",
                    FileAssetVersion.organization_id == self._actor.organization_id,
                    FileAssetVersion.scan_status == "clean",
                )
            ).all()
            return tuple(
                AssetContextItem(
                    source_id=asset.id,
                    source_version_id=version.id,
                    media_type=version.mime_type,
                    content_hash=version.sha256,
                    facts={
                        "storage_key": version.storage_key,
                        "mime_type": version.mime_type,
                        "metadata": version.metadata_json,
                    },
                )
                for asset, version in rows
            )
        return ()

    def authorize_target_slots(
        self,
        definition: RuntimeNodeDefinition,
        execution: WorkflowExecutionContext,
    ) -> TargetSlotAuthorization | None:
        binding = definition.node_binding
        persistence = cast(object, binding.get("output_persistence"))
        if not isinstance(persistence, Mapping):
            return None
        typed_persistence = cast(Mapping[str, Any], persistence)
        package = cast(object, typed_persistence.get("creation_package"))
        if not isinstance(package, Mapping):
            return None
        typed_package = cast(Mapping[str, Any], package)
        target_rules = cast(object, typed_package.get("target_rules"))
        if not isinstance(target_rules, Mapping):
            raise AssetExecutionPortError(
                "NODE_EXECUTION_TARGET_RULES_INVALID",
                "the package target rules are not declared",
            )
        typed_target_rules = cast(Mapping[str, Any], target_rules)
        prefix = typed_target_rules.get("target_slot_prefix")
        if type(prefix) is not str or not prefix:
            raise AssetExecutionPortError(
                "NODE_EXECUTION_TARGET_RULES_INVALID",
                "the package target-slot namespace is invalid",
            )
        statement = select(ProjectAssetSlot.slot_key).where(
            ProjectAssetSlot.organization_id == self._actor.organization_id,
            ProjectAssetSlot.project_id == execution.project_id,
            ProjectAssetSlot.deleted_at.is_(None),
            ProjectAssetSlot.slot_key.startswith(prefix),
        )
        if execution.lesson_unit_id is None:
            statement = statement.where(ProjectAssetSlot.lesson_unit_id.is_(None))
        else:
            statement = statement.where(ProjectAssetSlot.lesson_unit_id == execution.lesson_unit_id)
        slots = tuple(self._session.scalars(statement.order_by(ProjectAssetSlot.slot_key)))
        if not slots:
            raise AssetExecutionPortError(
                "NODE_EXECUTION_TARGET_SLOTS_MISSING",
                "the project has no authorized slots for the package namespace",
            )
        assert execution.branch_key is not None
        return TargetSlotAuthorization(
            content_release_id=definition.content_release_id,
            workflow_definition_version_id=definition.workflow_definition_version_id,
            project_id=execution.project_id,
            node_key=execution.node_key,
            branch_key=execution.branch_key,
            lesson_unit_id=execution.lesson_unit_id,
            slots=slots,
        )

    def freeze_reference_assets(
        self,
        definition: RuntimeNodeDefinition,
        execution: WorkflowExecutionContext,
    ) -> ReferenceAssetAuthorization | None:
        raw_policy = cast(object, definition.node_binding.get("reference_asset_policy"))
        if not isinstance(raw_policy, Mapping):
            raise AssetExecutionPortError(
                "NODE_EXECUTION_REFERENCE_ASSET_POLICY_INVALID",
                "the published reference asset policy is invalid",
            )
        policy = cast(Mapping[str, Any], raw_policy)
        mode = policy.get("mode")
        roles = policy.get("roles")
        if mode == "none" and roles in ([], ()):
            return None
        if mode not in {"optional", "required"} or not isinstance(roles, (list, tuple)):
            raise AssetExecutionPortError(
                "NODE_EXECUTION_REFERENCE_ASSET_POLICY_INVALID",
                "the published reference asset policy is invalid",
            )
        typed_roles = cast(Sequence[object], roles)
        if mode == "required" or any(_role_requires_asset(role) for role in typed_roles):
            raise AssetExecutionPortError(
                "NODE_EXECUTION_REFERENCE_ASSETS_MISSING",
                "required reference assets were not fixed before execution",
            )
        assert execution.branch_key is not None
        return ReferenceAssetAuthorization(
            content_release_id=definition.content_release_id,
            workflow_definition_version_id=definition.workflow_definition_version_id,
            project_id=execution.project_id,
            node_key=execution.node_key,
            branch_key=execution.branch_key,
            lesson_unit_id=execution.lesson_unit_id,
            assets=(),
        )


def _hash_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _role_requires_asset(value: object) -> bool:
    if not isinstance(value, Mapping):
        raise AssetExecutionPortError(
            "NODE_EXECUTION_REFERENCE_ASSET_POLICY_INVALID",
            "the published reference asset role is invalid",
        )
    role = cast(Mapping[str, object], value)
    minimum = role.get("min_items")
    if type(minimum) is not int:
        raise AssetExecutionPortError(
            "NODE_EXECUTION_REFERENCE_ASSET_POLICY_INVALID",
            "the published reference asset role minimum is invalid",
        )
    return minimum > 0
