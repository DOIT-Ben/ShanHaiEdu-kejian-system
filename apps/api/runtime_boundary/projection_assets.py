"""Trusted reference-asset projection for creation packages."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from apps.api.runtime_boundary.ports import (
    CreationPackageReferenceAssetSpec,
)
from apps.api.runtime_boundary.projection_values import (
    OutputProjectionError,
    require_json_mapping,
    require_text,
)


def compile_reference_assets(
    value: object, runtime: Mapping[str, Any]
) -> tuple[CreationPackageReferenceAssetSpec, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_INVALID",
            "reference_assets must resolve to an array",
        )
    raw_values = tuple(cast(Sequence[object], value))
    if len(raw_values) > 100:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_INVALID",
            "reference assets exceed the maximum count",
        )
    result = tuple(_compile_reference_asset(raw) for raw in raw_values)
    identities = [item.asset_version_id for item in result]
    if len(set(identities)) != len(identities):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_INVALID",
            "reference asset versions must be unique regardless of role",
        )
    if result and not _reference_assets_are_authorized(result, runtime):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSETS_UNAUTHORIZED",
            "reference assets are not in the trusted runtime authorization set",
        )
    return result


def _reference_assets_are_authorized(
    assets: Sequence[CreationPackageReferenceAssetSpec], runtime: Mapping[str, Any]
) -> bool:
    raw_allowed = runtime.get("reference_asset_version_ids")
    if not isinstance(raw_allowed, Sequence) or isinstance(raw_allowed, (str, bytes, bytearray)):
        return False
    try:
        allowed = {UUID(str(value)) for value in cast(Sequence[object], raw_allowed)}
    except (TypeError, ValueError):
        return False
    return {asset.asset_version_id for asset in assets} <= allowed


def _compile_reference_asset(raw: object) -> CreationPackageReferenceAssetSpec:
    item = require_json_mapping(raw, "OUTPUT_PROJECTION_REFERENCE_ASSET_INVALID")
    try:
        asset_id = UUID(str(item["asset_version_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_REFERENCE_ASSET_INVALID",
            "reference asset version ID is invalid",
        ) from exc
    return CreationPackageReferenceAssetSpec(
        asset_version_id=asset_id,
        role=require_text(item.get("role"), "reference asset role", 160),
    )
