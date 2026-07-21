"""Trusted authorization checks for package target slots."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.api.runtime_boundary.ports import (
    ReferenceAssetAuthorization,
    RuntimeNodeDefinition,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)
from apps.api.runtime_boundary.projection_values import (
    OutputProjectionError,
    plain_json_value,
    require_mapping,
    require_text_sequence,
)


def validate_target_slot_authorization(
    value: TargetSlotAuthorization | None,
    *,
    definition: RuntimeNodeDefinition,
    execution: WorkflowExecutionContext,
    required: bool,
) -> TargetSlotAuthorization | None:
    if value is None:
        if required:
            raise OutputProjectionError(
                "OUTPUT_PROJECTION_TARGET_SLOTS_MISSING",
                "package compilation requires an authorized target-slot set",
            )
        return None
    if type(value) is not TargetSlotAuthorization:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_SLOTS_INVALID",
            "authorized target slots must use the trusted DTO",
        )
    if (
        value.content_release_id != definition.content_release_id
        or value.workflow_definition_version_id != definition.workflow_definition_version_id
        or value.project_id != execution.project_id
        or value.node_key != execution.node_key
        or value.branch_key != execution.branch_key
        or value.lesson_unit_id != execution.lesson_unit_id
        or execution.content_release_id != value.content_release_id
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_SLOTS_MISMATCH",
            "target-slot authorization does not match release or execution",
        )
    return value


def validate_reference_asset_authorization(
    value: ReferenceAssetAuthorization | None,
    *,
    definition: RuntimeNodeDefinition,
    execution: WorkflowExecutionContext,
) -> ReferenceAssetAuthorization | None:
    if value is None:
        return None
    if type(value) is not ReferenceAssetAuthorization:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED",
            "reference assets must use the trusted authorization DTO",
        )
    if (
        value.content_release_id != definition.content_release_id
        or value.workflow_definition_version_id != definition.workflow_definition_version_id
        or value.project_id != execution.project_id
        or value.node_key != execution.node_key
        or value.branch_key != execution.branch_key
        or value.lesson_unit_id != execution.lesson_unit_id
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED",
            "reference asset authorization does not match release, project, or node",
        )
    return value


def validate_package_contract(
    binding: Mapping[str, Any], package: Mapping[str, Any] | None
) -> None:
    outputs = require_text_sequence(
        binding.get("output_contract_refs"),
        "OUTPUT_PROJECTION_OUTPUT_CONTRACTS_INVALID",
    )
    package_outputs = tuple(ref for ref in outputs if ref.startswith("package:"))
    if package is None and package_outputs:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_PACKAGE_DECLARATION_MISSING",
            "package output requires exactly one package declaration",
        )
    if package is not None and len(package_outputs) != 1:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_PACKAGE_OUTPUT_MISMATCH",
            "a package declaration must map to exactly one package output",
        )
    if package is None:
        return
    validate_reference_asset_projection(package)


def validate_reference_asset_projection(package: Mapping[str, Any]) -> None:
    """Require package reference assets to come from the typed runtime authorization."""

    item_mapping = require_mapping(
        package.get("item_mapping"),
        "OUTPUT_PROJECTION_ITEM_MAPPING_INVALID",
    )
    reference_assets = require_mapping(
        item_mapping.get("reference_assets"),
        "OUTPUT_PROJECTION_REFERENCE_ASSET_SOURCE_INVALID",
    )
    normalized = plain_json_value(reference_assets)
    allowed = normalized == {
        "source": "runtime",
        "pointer": "/reference_assets",
    } or normalized == {"source": "constant", "value": []}
    if not allowed:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSET_SOURCE_INVALID",
            "reference assets must use the trusted runtime set or an empty constant",
        )
