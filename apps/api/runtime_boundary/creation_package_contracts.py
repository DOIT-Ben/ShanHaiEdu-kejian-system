"""Immutable CreationPackage DTOs used by the runtime boundary."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from apps.api.artifacts.domain import ArtifactInvariantError
from apps.api.runtime_boundary.contract_values import (
    freeze_json_value,
    require_content_hash,
    require_text,
    require_uuid,
    require_uuid_fields,
)

_ALLOWED_REPLACE_MODES = frozenset({"reject_if_occupied", "replace_active", "append"})
_ALLOWED_PACKAGE_STATUSES = frozenset({"building", "ready", "invalid", "expired"})
_BASE_TARGET_RULE_KEYS = frozenset({"replace_modes", "allow_download"})
_TARGET_SLOT_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
MAX_PACKAGE_ITEMS = 100
MAX_REFERENCE_ASSETS = 20


@dataclass(frozen=True, slots=True)
class CreationPackageReferenceAssetSpec:
    asset_version_id: UUID
    role: str

    def __post_init__(self) -> None:
        require_uuid(self.asset_version_id, "creation package asset version is invalid")
        require_text(self.role, "creation package asset role is invalid", 160)


@dataclass(frozen=True, slots=True)
class CreationPackageItemSpec:
    item_key: str
    position: int
    title: str
    business_prompt: str
    prompt: Mapping[str, Any]
    reference_assets: tuple[CreationPackageReferenceAssetSpec, ...]
    output_spec: Mapping[str, Any]
    target_slot_key: str
    consistency_key: str | None

    def __post_init__(self) -> None:
        require_text(self.item_key, "creation package item_key is invalid", 160)
        if type(self.position) is not int or isinstance(self.position, bool) or self.position < 1:
            raise ArtifactInvariantError("creation package item position is invalid")
        require_text(self.title, "creation package item title is invalid", 255)
        require_text(
            self.business_prompt,
            "creation package business prompt is invalid",
            50_000,
        )
        raw_prompt = cast(object, self.prompt)
        raw_output_spec = cast(object, self.output_spec)
        if not isinstance(raw_prompt, Mapping) or not isinstance(raw_output_spec, Mapping):
            raise ArtifactInvariantError("creation package item mappings are invalid")
        assets = tuple(self.reference_assets)
        if any(type(item) is not CreationPackageReferenceAssetSpec for item in assets):
            raise ArtifactInvariantError("creation package reference assets are invalid")
        if len(assets) > MAX_REFERENCE_ASSETS:
            raise ArtifactInvariantError("creation package reference assets exceed the maximum")
        if len({asset.asset_version_id for asset in assets}) != len(assets):
            raise ArtifactInvariantError("creation package reference asset IDs must be unique")
        if (
            type(self.target_slot_key) is not str
            or len(self.target_slot_key) > 160
            or _TARGET_SLOT_PATTERN.fullmatch(self.target_slot_key) is None
        ):
            raise ArtifactInvariantError("creation package target slot is invalid")
        if self.consistency_key is not None:
            require_text(
                self.consistency_key,
                "creation package consistency key is invalid",
                160,
            )
        object.__setattr__(self, "reference_assets", assets)
        object.__setattr__(self, "prompt", freeze_json_value(self.prompt))
        object.__setattr__(self, "output_spec", freeze_json_value(self.output_spec))


def _validate_package_items(value: object) -> tuple[CreationPackageItemSpec, ...]:
    try:
        items = tuple(cast(Sequence[object], value))
    except TypeError as exc:
        raise ArtifactInvariantError("creation package items are invalid") from exc
    if (
        not items
        or len(items) > MAX_PACKAGE_ITEMS
        or any(type(item) is not CreationPackageItemSpec for item in items)
    ):
        raise ArtifactInvariantError("creation package items are invalid")
    typed_items = tuple(cast(CreationPackageItemSpec, item) for item in items)
    if len({item.item_key for item in typed_items}) != len(typed_items):
        raise ArtifactInvariantError("creation package item keys must be unique")
    if len({item.position for item in typed_items}) != len(typed_items):
        raise ArtifactInvariantError("creation package item positions must be unique")
    if tuple(item.position for item in typed_items) != tuple(range(1, len(typed_items) + 1)):
        raise ArtifactInvariantError("creation package items must use contiguous positions")
    if len({item.target_slot_key for item in typed_items}) != len(typed_items):
        raise ArtifactInvariantError("creation package target slots must be unique")
    return typed_items


def _validate_package_target_rules(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ArtifactInvariantError("creation package target rules are invalid")
    rules = cast(Mapping[str, Any], value)
    if set(rules) != set(_BASE_TARGET_RULE_KEYS):
        raise ArtifactInvariantError("creation package target rules are invalid")
    raw_modes = cast(object, rules["replace_modes"])
    if not isinstance(raw_modes, (list, tuple)):
        raise ArtifactInvariantError("creation package replace modes are invalid")
    modes = tuple(cast(Sequence[object], raw_modes))
    if not modes or any(
        type(mode) is not str or mode not in _ALLOWED_REPLACE_MODES for mode in modes
    ):
        raise ArtifactInvariantError("creation package replace modes are invalid")
    if len(set(modes)) != len(modes):
        raise ArtifactInvariantError("creation package replace modes must be unique")
    if type(rules["allow_download"]) is not bool:
        raise ArtifactInvariantError("creation package allow_download is invalid")


@dataclass(frozen=True, slots=True)
class TargetSlotAuthorization:
    """Release-bound allowlist supplied by the trusted target-slot resolver."""

    content_release_id: UUID
    workflow_definition_version_id: UUID
    project_id: UUID
    node_key: str
    branch_key: str
    lesson_unit_id: UUID | None
    slots: tuple[str, ...]

    def __post_init__(self) -> None:
        require_uuid_fields(
            (self.content_release_id, "target-slot release is invalid"),
            (self.workflow_definition_version_id, "target-slot workflow version is invalid"),
            (self.project_id, "target-slot project is invalid"),
        )
        require_text(self.node_key, "target-slot node is invalid", 160)
        require_text(self.branch_key, "target-slot branch is invalid", 80)
        if self.lesson_unit_id is not None:
            require_uuid(self.lesson_unit_id, "target-slot lesson unit is invalid")
        raw_slots = tuple(self.slots)
        if not raw_slots or any(
            type(slot) is not str or len(slot) > 160 or _TARGET_SLOT_PATTERN.fullmatch(slot) is None
            for slot in raw_slots
        ):
            raise ArtifactInvariantError("target-slot authorization is invalid")
        if len(set(raw_slots)) != len(raw_slots):
            raise ArtifactInvariantError("target-slot authorization must be unique")
        object.__setattr__(self, "slots", tuple(sorted(raw_slots)))


@dataclass(frozen=True, slots=True)
class ReferenceAssetAuthorization:
    """Project- and node-bound allowlist supplied by the trusted asset resolver."""

    content_release_id: UUID
    workflow_definition_version_id: UUID
    project_id: UUID
    node_key: str
    branch_key: str
    lesson_unit_id: UUID | None
    assets: tuple[CreationPackageReferenceAssetSpec, ...]

    def __post_init__(self) -> None:
        require_uuid_fields(
            (self.content_release_id, "reference asset release is invalid"),
            (self.workflow_definition_version_id, "reference asset workflow is invalid"),
            (self.project_id, "reference asset project is invalid"),
        )
        require_text(self.node_key, "reference asset node is invalid", 160)
        require_text(self.branch_key, "reference asset branch is invalid", 80)
        if self.lesson_unit_id is not None:
            require_uuid(self.lesson_unit_id, "reference asset lesson unit is invalid")
        assets = tuple(self.assets)
        if len(assets) > MAX_REFERENCE_ASSETS or any(
            type(value) is not CreationPackageReferenceAssetSpec for value in assets
        ):
            raise ArtifactInvariantError("reference asset authorization entries are invalid")
        if len({asset.asset_version_id for asset in assets}) != len(assets):
            raise ArtifactInvariantError("reference asset authorization IDs must be unique")
        object.__setattr__(self, "assets", assets)


@dataclass(frozen=True, slots=True)
class CreationPackageSpec:
    project_id: UUID
    workflow_run_id: UUID
    node_run_id: UUID
    lesson_unit_id: UUID | None
    artifact_version_id: UUID
    context_snapshot_id: UUID
    prompt_snapshot_id: UUID
    package_key: str
    package_type: str
    items: tuple[CreationPackageItemSpec, ...]
    target_rules: Mapping[str, Any]
    request_id: str

    def __post_init__(self) -> None:
        require_uuid_fields(
            (self.project_id, "creation package project is invalid"),
            (self.workflow_run_id, "creation package workflow run is invalid"),
            (self.node_run_id, "creation package node run is invalid"),
            (self.artifact_version_id, "creation package artifact version is invalid"),
            (self.context_snapshot_id, "creation package context snapshot is invalid"),
            (self.prompt_snapshot_id, "creation package prompt snapshot is invalid"),
        )
        if self.lesson_unit_id is not None:
            require_uuid(self.lesson_unit_id, "creation package lesson unit is invalid")
        require_text(self.package_key, "creation package key is invalid", 180)
        if not self.package_key.endswith(f":{self.artifact_version_id}"):
            raise ArtifactInvariantError("creation package key is not bound to its artifact")
        if self.package_type not in {"image", "video", "presentation"}:
            raise ArtifactInvariantError("creation package type is invalid")
        items = _validate_package_items(self.items)
        _validate_package_target_rules(self.target_rules)
        require_text(self.request_id, "creation package request_id is invalid", 256)
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "target_rules", freeze_json_value(self.target_rules))

    @property
    def target_slots(self) -> tuple[str, ...]:
        """Return fixed target slots without allowing callers to mutate the spec."""

        return tuple(item.target_slot_key for item in self.items)


@dataclass(frozen=True, slots=True)
class CreationPackageWriteResult:
    creation_package_id: UUID
    status: str
    content_hash: str

    def __post_init__(self) -> None:
        require_uuid(self.creation_package_id, "creation package result ID is invalid")
        if self.status not in _ALLOWED_PACKAGE_STATUSES:
            raise ArtifactInvariantError("creation package result status is invalid")
        require_content_hash(
            self.content_hash,
            "creation package result content hash is invalid",
        )
