"""Creation-package materialization for compiled runtime output projections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from apps.api.runtime_boundary.ports import (
    ArtifactWriteResult,
    CreationPackageItemSpec,
    CreationPackageSpec,
    FrozenSnapshotRefs,
    GeneratedArtifactWrite,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)
from apps.api.runtime_boundary.projection_assets import compile_reference_assets
from apps.api.runtime_boundary.projection_values import (
    OutputProjectionError,
    freeze_json_mapping,
    optional_text,
    require_json_mapping,
    require_mapping,
    require_position,
    require_text,
    resolve_json_pointer,
    resolve_projection,
    runtime_document,
)

MAX_PACKAGE_ITEMS = 100
_BASE_TARGET_RULE_KEYS = frozenset({"replace_modes", "allow_download"})
_ALLOWED_REPLACE_MODES = frozenset({"reject_if_occupied", "replace_active", "append"})


@dataclass(frozen=True, slots=True)
class OutputProjectionPlan:
    """Artifact DTO plus the immutable declaration needed for phase two."""

    artifact_write: GeneratedArtifactWrite
    package_declaration: Mapping[str, Any] | None
    output: Mapping[str, Any]
    execution: WorkflowExecutionContext
    snapshots: FrozenSnapshotRefs
    request_id: str
    runtime_values: Mapping[str, Any]
    target_slot_authorization: TargetSlotAuthorization | None = None

    def __post_init__(self) -> None:
        if self.package_declaration is not None:
            object.__setattr__(
                self,
                "package_declaration",
                freeze_json_mapping(self.package_declaration),
            )
        object.__setattr__(self, "output", freeze_json_mapping(self.output))
        object.__setattr__(self, "runtime_values", freeze_json_mapping(self.runtime_values))


def materialize_creation_package(
    plan: OutputProjectionPlan,
    *,
    artifact_result: ArtifactWriteResult,
) -> CreationPackageSpec | None:
    """Materialize a package after ArtifactPort returns its version ID."""

    declaration = plan.package_declaration
    if declaration is None:
        return None
    artifact_version_id = _require_artifact_version_id(artifact_result)
    package_type = _require_package_type(declaration.get("package_type"))
    package_key = _compile_package_key(declaration.get("package_key"), artifact_version_id)
    raw_items = _resolve_package_items(declaration, plan.output)
    mapping = require_mapping(
        declaration.get("item_mapping"),
        "OUTPUT_PROJECTION_ITEM_MAPPING_INVALID",
    )
    target_rules = _require_target_rules(declaration.get("target_rules"))
    authorization = plan.target_slot_authorization
    if authorization is None:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_SLOTS_MISSING",
            "package materialization requires an authorized target-slot set",
        )
    runtime = runtime_document(plan.execution, plan.runtime_values)
    items = _compile_package_items(
        raw_items,
        mapping=mapping,
        output=plan.output,
        runtime=runtime,
        target_rules=target_rules,
        allowed_target_slots=authorization.slots,
    )
    public_target_rules = _public_target_rules(target_rules)
    return _build_package_spec(
        plan,
        artifact_version_id=artifact_version_id,
        package_type=package_type,
        package_key=package_key,
        items=items,
        target_rules=public_target_rules,
    )


def _require_artifact_version_id(result: ArtifactWriteResult) -> UUID:
    value = cast(object, result.artifact_version_id)
    if not isinstance(value, UUID):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_ARTIFACT_RESULT_INVALID",
            "artifact result version ID is invalid",
        )
    return value


def _require_package_type(value: object) -> str:
    package_type = require_text(value, "package_type", 20)
    if package_type not in {"image", "video", "presentation"}:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_PACKAGE_TYPE_INVALID",
            "creation package type is unsupported",
        )
    return package_type


def _compile_package_key(raw: object, artifact_version_id: UUID) -> str:
    declaration = require_mapping(raw, "OUTPUT_PROJECTION_PACKAGE_KEY_INVALID")
    if declaration.get("strategy") != "source_artifact_version":
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_PACKAGE_KEY_INVALID",
            "package key strategy is unsupported",
        )
    prefix = require_text(declaration.get("prefix"), "package key prefix", 120)
    return require_text(f"{prefix}:{artifact_version_id}", "package_key", 180)


def _resolve_package_items(
    declaration: Mapping[str, Any], output: Mapping[str, Any]
) -> tuple[object, ...]:
    pointer = declaration.get("items_pointer")
    if not isinstance(pointer, str):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POINTER_INVALID",
            "package items_pointer must be a string",
        )
    raw_items = resolve_json_pointer(output, pointer, source="output")
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes, bytearray)):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_ITEMS_TYPE_INVALID",
            "package items projection must resolve to an array",
        )
    values = tuple(cast(Sequence[object], raw_items))
    if not values or len(values) > MAX_PACKAGE_ITEMS:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_ITEMS_INVALID",
            "package items must contain between one and one hundred entries",
        )
    return values


def _compile_package_items(
    raw_items: Sequence[object],
    *,
    mapping: Mapping[str, Any],
    output: Mapping[str, Any],
    runtime: Mapping[str, Any],
    target_rules: Mapping[str, Any],
    allowed_target_slots: Sequence[str],
) -> tuple[CreationPackageItemSpec, ...]:
    items = tuple(
        _compile_package_item(
            raw,
            position=index,
            mapping=mapping,
            output=output,
            runtime=runtime,
            target_rules=target_rules,
            allowed_target_slots=allowed_target_slots,
        )
        for index, raw in enumerate(raw_items, start=1)
    )
    _require_unique_package_values(items)
    return items


def _compile_package_item(
    raw_item: object,
    *,
    position: int,
    mapping: Mapping[str, Any],
    output: Mapping[str, Any],
    runtime: Mapping[str, Any],
    target_rules: Mapping[str, Any],
    allowed_target_slots: Sequence[str],
) -> CreationPackageItemSpec:
    item = require_json_mapping(raw_item, "OUTPUT_PROJECTION_ITEM_INVALID")
    item_runtime = {**runtime, "item_position": position}
    values = _project_item_values(mapping, output=output, item=item, runtime=item_runtime)
    target_slot = require_text(values["target_slot"], "target_slot", 160)
    _require_authorized_target_slot(target_slot, target_rules, allowed_target_slots)
    return CreationPackageItemSpec(
        item_key=require_text(values["item_key"], "item_key", 160),
        position=require_position(values["position"]),
        title=require_text(values["title"], "title", 255),
        business_prompt=require_text(values["business_prompt"], "business_prompt", 50_000),
        prompt=_project_prompt(mapping, output=output, item=item, runtime=item_runtime),
        reference_assets=compile_reference_assets(values["reference_assets"], runtime),
        output_spec=require_json_mapping(
            values["output_spec"], "OUTPUT_PROJECTION_OUTPUT_SPEC_INVALID"
        ),
        target_slot_key=target_slot,
        consistency_key=optional_text(values["consistency_key"], "consistency_key", 160),
    )


def _project_item_values(
    mapping: Mapping[str, Any],
    *,
    output: Mapping[str, Any],
    item: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> dict[str, object]:
    names = (
        "item_key",
        "position",
        "title",
        "business_prompt",
        "reference_assets",
        "output_spec",
        "target_slot",
        "consistency_key",
    )
    return {
        name: resolve_projection(mapping.get(name), output=output, item=item, runtime=runtime)
        for name in names
    }


def _project_prompt(
    mapping: Mapping[str, Any],
    *,
    output: Mapping[str, Any],
    item: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> Mapping[str, Any]:
    if "prompt" not in mapping:
        return {}
    return require_json_mapping(
        resolve_projection(mapping["prompt"], output=output, item=item, runtime=runtime),
        "OUTPUT_PROJECTION_PROMPT_INVALID",
    )


def _require_authorized_target_slot(
    target_slot: str,
    target_rules: Mapping[str, Any],
    allowed_target_slots: Sequence[str],
) -> None:
    prefix = cast(str, target_rules["target_slot_prefix"])
    if target_slot not in allowed_target_slots or not target_slot.startswith(prefix):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_SLOT_UNAUTHORIZED",
            "package target slot is outside the declared namespace",
        )


def _require_unique_package_values(items: Sequence[CreationPackageItemSpec]) -> None:
    for field, values in (
        ("item_key", [item.item_key for item in items]),
        ("position", [item.position for item in items]),
        ("target_slot", [item.target_slot_key for item in items]),
    ):
        if len(set(values)) != len(values):
            raise OutputProjectionError(
                "OUTPUT_PROJECTION_PACKAGE_DUPLICATE",
                f"package {field} values must be unique",
            )
    if [item.position for item in items] != list(range(1, len(items) + 1)):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_PACKAGE_POSITION_INVALID",
            "package item positions must be contiguous and ordered",
        )


def _require_target_rules(value: object) -> dict[str, Any]:
    rules = require_mapping(value, "OUTPUT_PROJECTION_TARGET_RULES_INVALID")
    keys = set(rules)
    allowed = _BASE_TARGET_RULE_KEYS | {"target_slot_prefix"}
    if not _BASE_TARGET_RULE_KEYS <= keys or keys - allowed:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_RULES_INVALID",
            "target_rules contains an unsupported shape",
        )
    modes = _require_replace_modes(rules.get("replace_modes"))
    allow_download = rules.get("allow_download")
    if type(allow_download) is not bool:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_RULES_INVALID",
            "allow_download must be a boolean",
        )
    result: dict[str, Any] = {
        "replace_modes": list(modes),
        "allow_download": allow_download,
    }
    if "target_slot_prefix" not in rules:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_RULES_INVALID",
            "target_rules must declare a target-slot namespace",
        )
    result["target_slot_prefix"] = require_text(
        rules.get("target_slot_prefix"), "target_slot_prefix", 160
    )
    return result


def _public_target_rules(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "replace_modes": list(cast(Sequence[object], value["replace_modes"])),
        "allow_download": value["allow_download"],
    }


def _require_replace_modes(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_RULES_INVALID",
            "replace_modes must be an array",
        )
    raw_modes = tuple(cast(Sequence[object], value))
    if any(type(mode) is not str for mode in raw_modes):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_RULES_INVALID",
            "replace_modes contains a non-string value",
        )
    modes = tuple(cast(str, mode) for mode in raw_modes)
    if (
        not modes
        or len(set(modes)) != len(modes)
        or any(mode not in _ALLOWED_REPLACE_MODES for mode in modes)
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_RULES_INVALID",
            "replace_modes contains an invalid or duplicate value",
        )
    return modes


def _build_package_spec(
    plan: OutputProjectionPlan,
    *,
    artifact_version_id: UUID,
    package_type: str,
    package_key: str,
    items: tuple[CreationPackageItemSpec, ...],
    target_rules: Mapping[str, Any],
) -> CreationPackageSpec:
    return CreationPackageSpec(
        project_id=plan.execution.project_id,
        workflow_run_id=plan.execution.workflow_run_id,
        node_run_id=plan.execution.node_run_id,
        lesson_unit_id=plan.execution.lesson_unit_id,
        artifact_version_id=artifact_version_id,
        context_snapshot_id=plan.snapshots.context_snapshot_id,
        prompt_snapshot_id=plan.snapshots.prompt_snapshot_id,
        package_key=package_key,
        package_type=package_type,
        items=items,
        target_rules=target_rules,
        request_id=plan.request_id,
    )
