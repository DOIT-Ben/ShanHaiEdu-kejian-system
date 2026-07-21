from __future__ import annotations

import pytest

from apps.api.content_runtime.authoring_policy import (
    AuthoringPolicyUnavailable,
    AuthoringViolation,
    compile_authoring_policy,
)


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
