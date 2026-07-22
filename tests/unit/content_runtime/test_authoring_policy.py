from __future__ import annotations

from pathlib import Path

import pytest

from apps.api.content_runtime.authoring_policy import (
    AuthoringPolicyUnavailable,
    AuthoringViolation,
)
from apps.api.content_runtime.authoring_policy_compiler import compile_authoring_policy
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from workflow.content_package import canonical_json_sha256

ROOT = Path(__file__).resolve().parents[3]


def _definition(*fields: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "content_definition",
        "spec": {
            "definition_key": "test.definition",
            "title": "Test definition",
            "fields": list(fields),
        },
    }


def _field(
    key: str,
    *,
    editable: bool,
    deletable: bool = False,
    field_type: str = "text",
    children: list[dict[str, object]] | None = None,
    repeatable: bool = False,
    min_items: int | None = None,
    max_items: int | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "field_key": key,
        "label": key,
        "type": field_type,
        "required": False,
        "editable": editable,
        "deletable": deletable,
    }
    if children is not None:
        value["children"] = children
    if repeatable:
        value["repeatable"] = True
    if min_items is not None:
        value["min_items"] = min_items
    if max_items is not None:
        value["max_items"] = max_items
    return value


def test_compile_rejects_definition_without_complete_authoring_strategy() -> None:
    legacy = {
        "kind": "content_definition",
        "spec": {
            "definition_key": "legacy.definition",
            "title": "Legacy",
            "fields": [{"field_key": "title", "type": "text"}],
        },
    }

    with pytest.raises(AuthoringPolicyUnavailable):
        compile_authoring_policy(legacy, checksum="a" * 64)


def test_create_and_update_keep_locked_values_immutable() -> None:
    policy = compile_authoring_policy(
        _definition(
            _field("stable_key", editable=False),
            _field("title", editable=True),
        ),
        checksum="a" * 64,
    )

    policy.validate_create({"title": "Initial"})
    with pytest.raises(AuthoringViolation) as create_error:
        policy.validate_create({"stable_key": "forged", "title": "Initial"})
    assert create_error.value.paths == ("stable_key",)

    policy.validate_update(
        {"stable_key": "stable", "title": "Initial"},
        {"stable_key": "stable", "title": "Edited"},
    )
    with pytest.raises(AuthoringViolation) as update_error:
        policy.validate_update(
            {"stable_key": "stable", "title": "Initial"},
            {"stable_key": "changed", "title": "Edited"},
        )
    assert update_error.value.paths == ("stable_key",)


def test_locked_ancestor_overrides_editable_child() -> None:
    policy = compile_authoring_policy(
        _definition(
            _field(
                "system_block",
                editable=False,
                field_type="object",
                children=[_field("description", editable=True)],
            )
        ),
        checksum="b" * 64,
    )

    with pytest.raises(AuthoringViolation):
        policy.validate_update(
            {"system_block": {"description": "before"}},
            {"system_block": {"description": "after"}},
        )


def test_repeatable_identity_is_locked_and_new_locked_items_require_provision() -> None:
    policy = compile_authoring_policy(
        _definition(
            _field(
                "items",
                editable=True,
                field_type="repeatable",
                repeatable=True,
                children=[
                    _field("item_key", editable=False),
                    _field("prompt", editable=True),
                ],
            )
        ),
        checksum="c" * 64,
    )

    policy.validate_update(
        {"items": [{"item_key": "one", "prompt": "before"}]},
        {"items": [{"item_key": "one", "prompt": "after"}]},
    )
    with pytest.raises(AuthoringViolation):
        policy.validate_update(
            {"items": [{"item_key": "one", "prompt": "before"}]},
            {"items": [{"item_key": "two", "prompt": "after"}]},
        )
    with pytest.raises(AuthoringViolation):
        policy.validate_update(
            {"items": [{"item_key": "one", "prompt": "before"}]},
            {
                "items": [
                    {"item_key": "one", "prompt": "after"},
                    {"item_key": "two", "prompt": "new"},
                ]
            },
        )


def test_repeatable_without_locked_descendants_can_add_items() -> None:
    policy = compile_authoring_policy(
        _definition(
            _field(
                "items",
                editable=True,
                deletable=True,
                field_type="repeatable",
                repeatable=True,
                children=[_field("prompt", editable=True)],
            )
        ),
        checksum="d" * 64,
    )

    policy.validate_update(
        {"items": [{"prompt": "before"}]},
        {"items": [{"prompt": "before"}, {"prompt": "new"}]},
    )


def test_server_provision_can_add_one_unique_locked_repeatable_item() -> None:
    policy = compile_authoring_policy(
        _definition(
            _field(
                "items",
                editable=True,
                field_type="repeatable",
                repeatable=True,
                children=[
                    _field("item_key", editable=False),
                    _field("prompt", editable=True),
                ],
            )
        ),
        checksum="e" * 64,
    )
    baseline = {"items": [{"item_key": "one", "prompt": "before"}]}
    candidate = {"items": [{"item_key": "one", "prompt": "edited"}]}

    provisioned = policy.provision_repeatable_item(
        baseline,
        candidate,
        field_path=("items",),
        item={"item_key": "two", "prompt": "new"},
    )
    assert provisioned["items"][-1] == {"item_key": "two", "prompt": "new"}

    with pytest.raises(AuthoringViolation):
        policy.provision_repeatable_item(
            baseline,
            candidate,
            field_path=("items",),
            item={"item_key": "one", "prompt": "duplicate"},
        )


def test_repeatable_reorder_duplicate_and_deletion_follow_quantity_policy() -> None:
    locked_children = [
        _field("item_key", editable=False),
        _field("prompt", editable=True),
    ]
    fixed = compile_authoring_policy(
        _definition(
            _field(
                "items",
                editable=True,
                deletable=False,
                field_type="repeatable",
                repeatable=True,
                min_items=1,
                max_items=2,
                children=locked_children,
            )
        ),
        checksum="f" * 64,
    )
    baseline = {
        "items": [
            {"item_key": "one", "prompt": "first"},
            {"item_key": "two", "prompt": "second"},
        ]
    }
    fixed.validate_update(
        baseline,
        {
            "items": [
                {"item_key": "two", "prompt": "edited"},
                {"item_key": "one", "prompt": "first"},
            ]
        },
    )
    with pytest.raises(AuthoringViolation):
        fixed.validate_update(
            baseline,
            {
                "items": [
                    {"item_key": "one", "prompt": "first"},
                    {"item_key": "one", "prompt": "duplicate"},
                ]
            },
        )
    fixed.validate_update(
        baseline,
        {"items": [{"item_key": "one", "prompt": "first"}]},
    )
    with pytest.raises(AuthoringViolation):
        fixed.validate_update(
            {"items": [{"item_key": "one", "prompt": "first"}]},
            {"items": []},
        )


def test_deletable_does_not_control_teacher_content_values() -> None:
    policy = compile_authoring_policy(
        _definition(_field("title", editable=True, deletable=False)),
        checksum="1" * 64,
    )

    policy.validate_update({"title": "before"}, {})


def test_nested_repeatables_validate_identity_at_each_level() -> None:
    policy = compile_authoring_policy(
        _definition(
            _field(
                "outer_items",
                editable=True,
                field_type="repeatable",
                repeatable=True,
                children=[
                    _field("outer_key", editable=False),
                    _field(
                        "inner_items",
                        editable=True,
                        field_type="repeatable",
                        repeatable=True,
                        min_items=1,
                        children=[
                            _field("inner_key", editable=False),
                            _field("text", editable=True),
                        ],
                    ),
                ],
            )
        ),
        checksum="2" * 64,
    )
    baseline = {
        "outer_items": [
            {
                "outer_key": "outer-1",
                "inner_items": [
                    {"inner_key": "inner-1", "text": "first"},
                    {"inner_key": "inner-2", "text": "second"},
                ],
            }
        ]
    }

    policy.validate_update(
        baseline,
        {
            "outer_items": [
                {
                    "outer_key": "outer-1",
                    "inner_items": [
                        {"inner_key": "inner-2", "text": "edited"},
                        {"inner_key": "inner-1", "text": "first"},
                    ],
                }
            ]
        },
    )
    policy.validate_update(
        baseline,
        {
            "outer_items": [
                {
                    "outer_key": "outer-1",
                    "inner_items": [{"inner_key": "inner-1", "text": "first"}],
                }
            ]
        },
    )
    with pytest.raises(AuthoringViolation):
        policy.validate_update(
            baseline,
            {
                "outer_items": [
                    {
                        "outer_key": "outer-1",
                        "inner_items": [
                            {"inner_key": "inner-1", "text": "first"},
                            {"inner_key": "inner-1", "text": "duplicate"},
                        ],
                    }
                ]
            },
        )

    parent_identity = policy.repeatable_item_identity(
        ("outer_items",),
        baseline["outer_items"][0],
    )
    provisioned = policy.provision_repeatable_item(
        baseline,
        baseline,
        field_path=("outer_items", "inner_items"),
        parent_identities=(parent_identity,),
        item={"inner_key": "inner-3", "text": "server provisioned"},
    )
    assert provisioned["outer_items"][0]["inner_items"][-1]["inner_key"] == "inner-3"
    with pytest.raises(AuthoringViolation):
        policy.provision_repeatable_item(
            baseline,
            baseline,
            field_path=("outer_items", "inner_items"),
            parent_identities=(parent_identity,),
            item={"inner_key": "inner-1", "text": "duplicate"},
        )
    with pytest.raises(AuthoringViolation):
        policy.validate_update(
            baseline,
            {
                "outer_items": [
                    {
                        "outer_key": "outer-1",
                        "inner_items": [
                            {"inner_key": "inner-1", "text": "first"},
                            {"inner_key": "inner-2", "text": "second"},
                            {"inner_key": "inner-3", "text": "new"},
                        ],
                    }
                ]
            },
        )


def test_all_current_builtin_definitions_compile_authoring_policy() -> None:
    source = load_builtin_courseware_release(ROOT)
    definitions = [
        item
        for key, item in source.items.items()
        if source.manifest_entries[key]["kind"] == "content_definition"
    ]

    policies = [
        compile_authoring_policy(item, checksum=canonical_json_sha256(item)) for item in definitions
    ]
    assert len(policies) == len(definitions)
    assert all(policy.fields for policy in policies)
