from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import ValidationError

from apps.api.main import create_app
from apps.api.projects.policy_schemas import UpdateAutomationPolicyRequest
from apps.api.settings import Settings
from tests.contract.test_stage0_contracts import (
    CONTRACTS,
    load_json,
    load_openapi,
    operations_by_id,
    resolve_external_refs,
    resolve_local,
    validate,
)

UUIDS = {
    "package": "018f1000-0000-7000-8000-000000000002",
    "project": "018f1000-0000-7000-8000-000000000003",
    "item": "018f1000-0000-7000-8000-000000000006",
    "prompt": "018f1000-0000-7000-8000-000000000021",
}


def operation_request_schema(operation_id: str) -> dict:
    openapi = load_openapi()
    operation = operations_by_id(openapi)[operation_id]
    schema = deepcopy(operation["requestBody"]["content"]["application/json"]["schema"])
    schema["components"] = deepcopy(openapi["components"])
    return resolve_external_refs(schema)


def assert_invalid(instance: dict, schema: dict) -> None:
    with pytest.raises(ValidationError):
        validate(instance, schema)


def test_execution_modes_share_a_new_policy_contract_without_removing_legacy_input() -> None:
    openapi = load_openapi()
    schemas = openapi["components"]["schemas"]
    assert schemas["AutomationPolicyMode"]["enum"] == ["guided", "automatic"]
    assert schemas["AutomationMode"]["deprecated"] is True
    assert schemas["AutomationMode"]["enum"] == ["manual", "assisted", "automatic"]
    assert "auto_select" in schemas["AutomationNodeRule"]["properties"]

    create_project = deepcopy(schemas["CreateProjectRequest"])
    create_project["components"] = deepcopy(openapi["components"])
    validate(
        {"title": "百分数", "knowledge_point": "百分数意义", "execution_mode": "guided"},
        create_project,
    )
    validate(
        {"title": "百分数", "knowledge_point": "百分数意义", "automation_mode": "assisted"},
        create_project,
    )
    assert_invalid(
        {
            "title": "百分数",
            "knowledge_point": "百分数意义",
            "execution_mode": "guided",
            "automation_mode": "assisted",
        },
        create_project,
    )
    assert {
        "getProjectAutomationPolicy",
        "updateProjectAutomationPolicy",
    }.issubset(operations_by_id(openapi))

    current_project = deepcopy(schemas["CurrentProject"])
    legacy_project = deepcopy(schemas["LegacyProject"])
    current_project["components"] = deepcopy(openapi["components"])
    legacy_project["components"] = deepcopy(openapi["components"])
    shared_project = {
        "id": UUIDS["project"],
        "title": "百分数",
        "subject": "primary_math",
        "knowledge_point": "百分数意义",
        "status": "active",
        "created_at": "2026-07-18T00:00:00Z",
        "updated_at": "2026-07-18T00:00:00Z",
    }
    validate({**shared_project, "execution_mode": "guided"}, current_project)
    validate({**shared_project, "automation_mode": "assisted"}, legacy_project)
    assert_invalid({**shared_project, "automation_mode": "assisted"}, current_project)

    explicit_selection = UpdateAutomationPolicyRequest(
        node_rules=[{"node_key": "intro.select", "auto_select": True}]
    )
    assert explicit_selection.node_rules is not None
    assert explicit_selection.node_rules[0].auto_select is True


def test_project_limits_and_policy_etags_match_runtime_contract() -> None:
    openapi = load_openapi()
    operations = operations_by_id(openapi)
    project_fields = openapi["components"]["schemas"]["CreateProjectRequest"]["properties"]
    assert project_fields["title"]["maxLength"] == 255
    assert project_fields["knowledge_point"]["maxLength"] == 255
    assert project_fields["grade"]["maxLength"] == 40
    assert project_fields["textbook_edition"]["maxLength"] == 120

    for operation_id in (
        "getProject",
        "getProjectAutomationPolicy",
        "updateProjectAutomationPolicy",
    ):
        assert "ETag" in operations[operation_id]["responses"]["200"]["headers"]

    runtime = create_app(settings=Settings(_env_file=None, environment="test")).openapi()
    runtime_operations = operations_by_id(runtime)
    runtime_schemas = runtime["components"]["schemas"]
    assert "auto_select" in runtime_schemas["AutomationNodeRule"]["properties"]
    assert (
        runtime_schemas["SavePromptVersionRequest"]["properties"]["reference_asset_version_ids"][
            "uniqueItems"
        ]
        is True
    )
    assert (
        runtime_schemas["LegacyGenerateCreationBatchRequest"]["properties"]["item_ids"][
            "uniqueItems"
        ]
        is True
    )
    update = runtime_operations["updateProjectAutomationPolicy"]
    parameters = {parameter["name"]: parameter for parameter in update["parameters"]}
    assert parameters["Idempotency-Key"]["schema"]["maxLength"] == 128
    for operation_id in (
        "getProject",
        "getProjectAutomationPolicy",
        "updateProjectAutomationPolicy",
    ):
        assert "ETag" in runtime_operations[operation_id]["responses"]["200"]["headers"]


def test_creation_batch_source_is_a_strict_discriminated_union() -> None:
    schema = operation_request_schema("createCreationBatch")
    validate(
        {
            "source_kind": "project",
            "studio_type": "image",
            "title": "PPT图片",
            "creation_package_id": UUIDS["package"],
        },
        schema,
    )
    validate(
        {"source_kind": "standalone", "studio_type": "image", "title": "独立图片"},
        schema,
    )
    validate(
        {
            "studio_type": "image",
            "title": "兼容旧客户端",
            "creation_package_id": UUIDS["package"],
        },
        schema,
    )

    assert_invalid(
        {"source_kind": "project", "studio_type": "image", "title": "缺少创作包"},
        schema,
    )

    openapi = load_openapi()
    response_schema = deepcopy(
        operations_by_id(openapi)["createCreationBatch"]["responses"]["201"]["content"][
            "application/json"
        ]["schema"]
    )
    response_schema["components"] = deepcopy(openapi["components"])
    project_batch = load_json(CONTRACTS / "fixtures/creation-lifecycle/project-batch-created.json")
    standalone_batch = load_json(
        CONTRACTS / "fixtures/creation-lifecycle/standalone-batch-created.json"
    )
    validate(project_batch, response_schema)
    validate(standalone_batch, response_schema)

    project_without_target = deepcopy(project_batch)
    del project_without_target["data"]["items"][0]["target_slot_key"]
    assert_invalid(project_without_target, response_schema)

    standalone_with_target = deepcopy(standalone_batch)
    standalone_with_target["data"]["items"] = [deepcopy(project_batch["data"]["items"][0])]
    assert_invalid(standalone_with_target, response_schema)
    assert_invalid(
        {
            "source_kind": "standalone",
            "studio_type": "image",
            "title": "伪造项目来源",
            "creation_package_id": UUIDS["package"],
        },
        schema,
    )


def test_four_creation_actions_have_independent_idempotent_operations() -> None:
    openapi = load_openapi()
    operations = operations_by_id(openapi)
    operation_ids = {
        "saveCreationPromptVersion",
        "generateCreationItem",
        "adoptGenerationResult",
        "saveAdoptionToProject",
    }
    assert operation_ids.issubset(operations)

    for operation_id in operation_ids:
        parameters = [
            resolve_local(openapi, item) for item in operations[operation_id]["parameters"]
        ]
        assert any(parameter.get("name") == "Idempotency-Key" for parameter in parameters)

    assert operations["saveGenerationResultToProject"]["deprecated"] is True


def test_project_save_rejects_target_override_and_standalone_requires_target() -> None:
    schema = operation_request_schema("saveAdoptionToProject")
    validate(
        {"source_kind": "project", "replace_mode": "replace_active"},
        schema,
    )
    assert_invalid(
        {
            "source_kind": "project",
            "project_id": UUIDS["project"],
            "slot_key": "lesson.01.ppt.page.05.main_visual",
            "replace_mode": "replace_active",
        },
        schema,
    )
    validate(
        {
            "source_kind": "standalone",
            "project_id": UUIDS["project"],
            "slot_key": "lesson.01.ppt.page.05.main_visual",
            "replace_mode": "replace_active",
        },
        schema,
    )
    assert_invalid(
        {"source_kind": "standalone", "replace_mode": "replace_active"},
        schema,
    )


def test_teacher_facing_creation_contract_does_not_expose_provider_fields() -> None:
    schemas = load_openapi()["components"]["schemas"]
    public_schema_names = {
        "CreateCreationBatchRequest",
        "CreationBatch",
        "SavePromptVersionRequest",
        "PromptVersion",
        "GenerateCreationItemRequest",
        "Adoption",
        "SaveAdoptionToProjectRequest",
    }
    rendered = repr({name: schemas[name] for name in public_schema_names}).lower()
    assert "provider_name" not in rendered
    assert "provider_model" not in rendered
    assert "secret" not in rendered


def test_creation_package_v2_requires_workflow_context_and_target_but_legacy_remains_valid() -> (
    None
):
    schema = resolve_external_refs(load_json(CONTRACTS / "creation-package.schema.json"))
    current = load_json(
        CONTRACTS / "fixtures/creation-lifecycle/project-creation-package-current.json"
    )
    validate(current, schema)

    missing_workflow = deepcopy(current)
    del missing_workflow["source"]["workflow_run_id"]
    assert_invalid(missing_workflow, schema)

    missing_source_node = deepcopy(current)
    del missing_source_node["source"]["source_node_run_id"]
    assert_invalid(missing_source_node, schema)

    missing_target = deepcopy(current)
    del missing_target["items"][0]["target_slot_key"]
    assert_invalid(missing_target, schema)

    legacy = {
        "package_id": UUIDS["package"],
        "package_type": "image",
        "status": "ready",
        "source": {
            "project_id": UUIDS["project"],
            "node_run_id": "018f1000-0000-7000-8000-000000000005",
        },
        "items": [
            {
                "item_key": "legacy-item",
                "position": 1,
                "title": "旧创作条目",
                "prompt": {},
                "output_spec": {},
            }
        ],
        "created_at": "2026-07-17T00:00:00Z",
    }
    validate(legacy, schema)


def test_creation_lifecycle_events_embed_the_canonical_sse_envelope() -> None:
    canonical = load_json(CONTRACTS / "sse-event.schema.json")
    lifecycle = load_json(CONTRACTS / "creation-lifecycle-event.schema.json")
    embedded = lifecycle["$defs"]["base_event"]

    for key in ("type", "additionalProperties", "required", "properties"):
        assert embedded[key] == canonical[key]


def test_artifact_stale_reason_contract_is_strict_and_supports_revoke() -> None:
    schema = resolve_external_refs(load_json(CONTRACTS / "artifact-stale-reason.schema.json"))
    reason = {
        "reason_code": "UPSTREAM_APPROVED_VERSION_CHANGED",
        "replaced_upstream_version_id": UUIDS["project"],
        "replacement_version_id": UUIDS["item"],
        "bindings": [
            {
                "relation_type": "derives_from",
                "binding_key": "lesson-scope",
                "impact_scope": {"mode": "all"},
            }
        ],
    }
    validate(reason, schema)

    revoke = deepcopy(reason)
    revoke["reason_code"] = "UPSTREAM_APPROVAL_REVOKED"
    revoke["replacement_version_id"] = None
    validate(revoke, schema)

    invalid = deepcopy(reason)
    invalid["bindings"][0]["impact_scope"] = {
        "mode": "keyed",
        "selector": "lesson_unit_key",
        "keys": ["LESSON-001"],
    }
    assert_invalid(invalid, schema)

    invalid = deepcopy(reason)
    invalid["bindings"][0]["impact_scope"] = {
        "mode": "all",
        "extra": True,
    }
    assert_invalid(invalid, schema)

    invalid = deepcopy(reason)
    invalid["reason_code"] = "UPSTREAM_APPROVAL_REVOKED"
    assert_invalid(invalid, schema)
