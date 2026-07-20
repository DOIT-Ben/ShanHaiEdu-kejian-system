"""Minimal ORM-free application ports required by Issue #89."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol, cast
from uuid import UUID

from apps.api.artifacts.domain import (
    ArtifactImpactScope,
    ArtifactInvariantError,
    ArtifactRelationType,
)
from apps.api.model_gateway.contracts import (
    ModelAuditContext,
    TextGatewayResult,
    TextModelRequest,
)
from apps.api.model_gateway.ports import CancellationToken
from workflow.node_state import NodeStatus
from workflow.prompt_runtime import AssembledContext, CompiledPrompt

_BASE_TARGET_RULE_KEYS = frozenset({"replace_modes", "allow_download"})
_ALLOWED_REPLACE_MODES = frozenset({"reject_if_occupied", "replace_active", "append"})
_TARGET_SLOT_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


class _FrozenDict(dict[str, Any]):
    """A JSON-serializable mapping whose mutators are disabled."""

    __slots__ = ()

    @staticmethod
    def _immutable(*args: object, **kwargs: object) -> None:
        raise TypeError("immutable JSON mapping")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable


def _freeze_json_value(value: object) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        entries = cast(Mapping[object, object], value)
        for key, child in entries.items():
            if type(key) is not str:
                raise ArtifactInvariantError("JSON mapping keys must be strings")
            frozen[key] = _freeze_json_value(child)
        result = _FrozenDict()
        dict.__init__(result, frozen)
        return result
    if isinstance(value, (list, tuple)):
        values = cast(Sequence[object], value)
        return tuple(_freeze_json_value(child) for child in values)
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ArtifactInvariantError("JSON values must be finite and JSON-compatible")


def _require_uuid(value: object, message: str) -> None:
    if not isinstance(value, UUID):
        raise ArtifactInvariantError(message)


def _require_uuid_fields(*fields: tuple[object, str]) -> None:
    for value, message in fields:
        _require_uuid(value, message)


@dataclass(frozen=True, slots=True)
class RuntimeNodeDefinition:
    content_release_id: UUID
    workflow_definition_version_id: UUID
    node_key: str
    execution_kind: str
    generation_template_key: str
    generation_template: Mapping[str, Any]
    node_binding: Mapping[str, Any]
    content_definition_version_id: UUID
    content_definition_release_id: UUID | None = None
    content_definition_item_key: str | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.content_definition_version_id, "content definition version is invalid")
        if self.content_definition_release_id is not None:
            _require_uuid(
                self.content_definition_release_id,
                "content definition release is invalid",
            )


@dataclass(frozen=True, slots=True)
class WorkflowExecutionContext:
    organization_id: UUID
    project_id: UUID
    workflow_run_id: UUID
    node_run_id: UUID
    content_release_id: UUID
    workflow_definition_version_id: UUID
    node_key: str
    branch_key: str | None
    lesson_key: str | None
    lesson_unit_id: UUID | None
    status: str


@dataclass(frozen=True, slots=True)
class ArtifactContextVersion:
    artifact_version_id: UUID
    artifact_type: str
    content: Mapping[str, Any]
    content_hash: str


@dataclass(frozen=True, slots=True)
class AssetContextItem:
    source_id: UUID
    source_version_id: UUID
    media_type: str
    content_hash: str
    facts: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class GeneratedArtifactRelation:
    from_artifact_version_id: UUID
    relation_type: ArtifactRelationType
    binding_key: str
    impact_scope: Mapping[str, Any]

    def __post_init__(self) -> None:
        raw_source_id = cast(object, self.from_artifact_version_id)
        if not isinstance(raw_source_id, UUID):
            raise ArtifactInvariantError("generated relation source version is invalid")
        raw_relation_type: object = self.relation_type
        if type(raw_relation_type) is not ArtifactRelationType:
            raise ArtifactInvariantError("generated relation type is invalid")
        raw_binding_key: object = self.binding_key
        if (
            type(raw_binding_key) is not str
            or not raw_binding_key.strip()
            or len(raw_binding_key) > 160
        ):
            raise ArtifactInvariantError("generated relation binding_key is invalid")
        scope = ArtifactImpactScope.from_mapping(self.impact_scope)
        canonical: dict[str, Any] = {"mode": scope.mode}
        if scope.mode == "keyed":
            assert scope.selector is not None
            canonical.update(selector=scope.selector.value, keys=scope.keys)
        object.__setattr__(self, "impact_scope", _freeze_json_value(canonical))


@dataclass(frozen=True, slots=True)
class GeneratedArtifactWrite:
    project_id: UUID
    lesson_unit_id: UUID | None
    node_run_id: UUID
    context_snapshot_id: UUID
    prompt_snapshot_id: UUID
    artifact_key: str
    artifact_type: str
    branch_key: str
    content_definition_version_id: UUID
    content: Mapping[str, Any]
    request_id: str
    relations: tuple[GeneratedArtifactRelation, ...] = ()

    def __post_init__(self) -> None:
        _require_uuid_fields(
            (self.project_id, "generated artifact project is invalid"),
            (self.node_run_id, "generated artifact node run is invalid"),
            (self.context_snapshot_id, "generated artifact context snapshot is invalid"),
            (self.prompt_snapshot_id, "generated artifact prompt snapshot is invalid"),
            (
                self.content_definition_version_id,
                "generated artifact content definition is invalid",
            ),
        )
        if self.lesson_unit_id is not None:
            _require_uuid(self.lesson_unit_id, "generated artifact lesson unit is invalid")
        relations: tuple[object, ...] = tuple(self.relations)
        if any(type(item) is not GeneratedArtifactRelation for item in relations):
            raise ArtifactInvariantError("generated artifact relations are invalid")
        object.__setattr__(self, "relations", relations)
        object.__setattr__(self, "content", _freeze_json_value(self.content))


@dataclass(frozen=True, slots=True)
class ArtifactWriteResult:
    artifact_id: UUID
    artifact_version_id: UUID
    content_hash: str
    project_id: UUID | None = None
    node_run_id: UUID | None = None
    artifact_key: str | None = None
    artifact_type: str | None = None
    branch_key: str | None = None
    lesson_unit_id: UUID | None = None
    content_definition_version_id: UUID | None = None

    def __post_init__(self) -> None:
        _require_uuid_fields(
            (self.artifact_id, "artifact write result artifact is invalid"),
            (self.artifact_version_id, "artifact write result version is invalid"),
        )
        for value, message in (
            (self.project_id, "artifact write result project is invalid"),
            (self.node_run_id, "artifact write result node run is invalid"),
            (self.lesson_unit_id, "artifact write result lesson unit is invalid"),
            (
                self.content_definition_version_id,
                "artifact write result content definition is invalid",
            ),
        ):
            if value is not None:
                _require_uuid(value, message)
        for value, message, maximum in (
            (self.artifact_key, "artifact write result artifact key is invalid", 160),
            (self.artifact_type, "artifact write result artifact type is invalid", 80),
            (self.branch_key, "artifact write result branch is invalid", 80),
        ):
            if value is not None and (
                type(value) is not str or not value.strip() or len(value) > maximum
            ):
                raise ArtifactInvariantError(message)


@dataclass(frozen=True, slots=True)
class FrozenSnapshotRefs:
    context_snapshot_id: UUID
    prompt_snapshot_id: UUID
    context_hash: str
    prompt_hash: str

    def __post_init__(self) -> None:
        _require_uuid_fields(
            (self.context_snapshot_id, "context snapshot is invalid"),
            (self.prompt_snapshot_id, "prompt snapshot is invalid"),
        )


@dataclass(frozen=True, slots=True)
class CreationPackageReferenceAssetSpec:
    asset_version_id: UUID
    role: str

    def __post_init__(self) -> None:
        _require_uuid(self.asset_version_id, "creation package asset version is invalid")
        if type(self.role) is not str or not self.role.strip() or len(self.role) > 160:
            raise ArtifactInvariantError("creation package asset role is invalid")


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
        if type(self.item_key) is not str or not self.item_key.strip() or len(self.item_key) > 160:
            raise ArtifactInvariantError("creation package item_key is invalid")
        if type(self.position) is not int or isinstance(self.position, bool) or self.position < 1:
            raise ArtifactInvariantError("creation package item position is invalid")
        if type(self.title) is not str or not self.title.strip() or len(self.title) > 255:
            raise ArtifactInvariantError("creation package item title is invalid")
        if (
            type(self.business_prompt) is not str
            or not self.business_prompt.strip()
            or len(self.business_prompt) > 50_000
        ):
            raise ArtifactInvariantError("creation package business prompt is invalid")
        raw_prompt = cast(object, self.prompt)
        raw_output_spec = cast(object, self.output_spec)
        if not isinstance(raw_prompt, Mapping) or not isinstance(raw_output_spec, Mapping):
            raise ArtifactInvariantError("creation package item mappings are invalid")
        assets = tuple(self.reference_assets)
        if any(type(item) is not CreationPackageReferenceAssetSpec for item in assets):
            raise ArtifactInvariantError("creation package reference assets are invalid")
        if (
            type(self.target_slot_key) is not str
            or not self.target_slot_key.strip()
            or len(self.target_slot_key) > 160
        ):
            raise ArtifactInvariantError("creation package target slot is invalid")
        if self.consistency_key is not None and (
            type(self.consistency_key) is not str
            or not self.consistency_key.strip()
            or len(self.consistency_key) > 160
        ):
            raise ArtifactInvariantError("creation package consistency key is invalid")
        object.__setattr__(self, "reference_assets", assets)
        object.__setattr__(self, "prompt", _freeze_json_value(self.prompt))
        object.__setattr__(self, "output_spec", _freeze_json_value(self.output_spec))


def _validate_package_items(value: object) -> tuple[CreationPackageItemSpec, ...]:
    try:
        items = tuple(cast(Sequence[object], value))
    except TypeError as exc:
        raise ArtifactInvariantError("creation package items are invalid") from exc
    if not items or any(type(item) is not CreationPackageItemSpec for item in items):
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
        _require_uuid(self.content_release_id, "target-slot release is invalid")
        _require_uuid(
            self.workflow_definition_version_id,
            "target-slot workflow version is invalid",
        )
        _require_uuid(self.project_id, "target-slot project is invalid")
        if type(self.node_key) is not str or not self.node_key.strip() or len(self.node_key) > 160:
            raise ArtifactInvariantError("target-slot node is invalid")
        if type(self.branch_key) is not str or not self.branch_key.strip() or len(self.branch_key) > 80:
            raise ArtifactInvariantError("target-slot branch is invalid")
        if self.lesson_unit_id is not None:
            _require_uuid(self.lesson_unit_id, "target-slot lesson unit is invalid")
        raw_slots = tuple(self.slots)
        if not raw_slots or any(
            type(slot) is not str
            or not slot.strip()
            or len(slot) > 160
            or _TARGET_SLOT_PATTERN.fullmatch(slot) is None
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
        for value, message in (
            (self.content_release_id, "reference asset release is invalid"),
            (self.workflow_definition_version_id, "reference asset workflow is invalid"),
            (self.project_id, "reference asset project is invalid"),
        ):
            _require_uuid(value, message)
        if type(self.node_key) is not str or not self.node_key.strip() or len(self.node_key) > 160:
            raise ArtifactInvariantError("reference asset node is invalid")
        if type(self.branch_key) is not str or not self.branch_key.strip() or len(self.branch_key) > 80:
            raise ArtifactInvariantError("reference asset branch is invalid")
        if self.lesson_unit_id is not None:
            _require_uuid(self.lesson_unit_id, "reference asset lesson unit is invalid")
        assets = tuple(self.assets)
        if any(type(value) is not CreationPackageReferenceAssetSpec for value in assets):
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
        for value, message in (
            (self.project_id, "creation package project is invalid"),
            (self.workflow_run_id, "creation package workflow run is invalid"),
            (self.node_run_id, "creation package node run is invalid"),
            (self.artifact_version_id, "creation package artifact version is invalid"),
            (self.context_snapshot_id, "creation package context snapshot is invalid"),
            (self.prompt_snapshot_id, "creation package prompt snapshot is invalid"),
        ):
            _require_uuid(value, message)
        if self.lesson_unit_id is not None:
            _require_uuid(self.lesson_unit_id, "creation package lesson unit is invalid")
        if (
            type(self.package_key) is not str
            or not self.package_key.strip()
            or len(self.package_key) > 180
        ):
            raise ArtifactInvariantError("creation package key is invalid")
        if self.package_type not in {"image", "video", "presentation"}:
            raise ArtifactInvariantError("creation package type is invalid")
        items = _validate_package_items(self.items)
        _validate_package_target_rules(self.target_rules)
        if type(self.request_id) is not str or not self.request_id.strip():
            raise ArtifactInvariantError("creation package request_id is invalid")
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "target_rules", _freeze_json_value(self.target_rules))

    @property
    def target_slots(self) -> tuple[str, ...]:
        """Return fixed target slots without allowing callers to mutate the spec."""

        return tuple(item.target_slot_key for item in self.items)


@dataclass(frozen=True, slots=True)
class CreationPackageWriteResult:
    creation_package_id: UUID
    status: str
    content_hash: str


class RuntimeDefinitionReader(Protocol):
    def resolve(self, node_run_id: UUID) -> RuntimeNodeDefinition: ...


class WorkflowExecutionPort(Protocol):
    def require_context(
        self, node_run_id: UUID, *, for_update: bool
    ) -> WorkflowExecutionContext: ...

    def transition(self, node_run_id: UUID, target: NodeStatus) -> None: ...


class ArtifactPort(Protocol):
    def list_context_versions(
        self, project_id: UUID, source: str
    ) -> tuple[ArtifactContextVersion, ...]: ...

    def persist_generated(self, write: GeneratedArtifactWrite) -> ArtifactWriteResult: ...


class AssetPort(Protocol):
    def list_context_items(self, project_id: UUID, source: str) -> tuple[AssetContextItem, ...]: ...


class PromptSnapshotPort(Protocol):
    def freeze(
        self,
        node_run_id: UUID,
        *,
        context: AssembledContext,
        prompt: CompiledPrompt,
    ) -> FrozenSnapshotRefs: ...


class ModelInvocationPort(Protocol):
    async def generate_text(
        self,
        request: TextModelRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> TextGatewayResult: ...


class CreationPackagePort(Protocol):
    def publish(self, spec: CreationPackageSpec) -> CreationPackageWriteResult: ...
