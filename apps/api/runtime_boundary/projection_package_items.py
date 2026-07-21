"""CreationPackage item projection and target-rule validation."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from apps.api.runtime_boundary.ports import CreationPackageItemSpec
from apps.api.runtime_boundary.projection_assets import compile_reference_assets
from apps.api.runtime_boundary.projection_values import (
    OutputProjectionError,
    optional_text,
    require_json_mapping,
    require_mapping,
    require_position,
    require_text,
    resolve_projection,
)

_ALLOWED_REPLACE_MODES = frozenset({"reject_if_occupied", "replace_active", "append"})
_BASE_TARGET_RULE_KEYS = frozenset({"replace_modes", "allow_download"})
_TARGET_SLOT_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_TARGET_SLOT_PREFIX_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*\.$")


def compile_package_items(
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
    if (
        _TARGET_SLOT_PATTERN.fullmatch(target_slot) is None
        or target_slot not in allowed_target_slots
        or not target_slot.startswith(prefix)
    ):
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


def require_target_rules(value: object) -> dict[str, Any]:
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
    target_slot_prefix = rules.get("target_slot_prefix")
    if (
        type(target_slot_prefix) is not str
        or not target_slot_prefix.strip()
        or len(target_slot_prefix) > 159
        or _TARGET_SLOT_PREFIX_PATTERN.fullmatch(target_slot_prefix) is None
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_TARGET_RULES_INVALID",
            "target_slot_prefix must be a semantic slot namespace",
        )
    result["target_slot_prefix"] = target_slot_prefix
    return result


def public_target_rules(value: Mapping[str, Any]) -> dict[str, Any]:
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
