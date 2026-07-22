from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from sqlalchemy import func, select

from apps.api.content_runtime.definition_projection import (
    build_content_json_schema,
    build_content_validation_rules,
)
from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackage,
    ContentPackageItemVersion,
    ContentPackageVersion,
    ContentRelease,
    ContentReleaseItem,
)
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import utc_now
from apps.api.ids import new_uuid7
from apps.api.projects.models import AutomationPolicy, Project
from apps.api.workflows.models import WorkflowDefinitionVersion
from workflow.content_package import canonical_json_sha256
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[2]


def ensure_test_authoring_definition(
    session,
    project_id,
    *,
    schema_id="https://shanhaiedu.local/contracts/content-definition.schema.json",
):
    project = session.get(Project, project_id)
    assert project is not None
    published = ContentReleasePublisher(session).publish(
        load_builtin_courseware_release(ROOT),
        published_by=project.owner_principal_id,
    )
    workflow_version_id = _ensure_test_authoring_workflow(
        session,
        published.workflow_definition_version_id,
    )
    _bind_test_workflow(session, project, workflow_version_id)
    existing = (
        session.query(ContentDefinitionVersion)
        .join(
            ContentReleaseItem,
            ContentReleaseItem.content_package_version_id
            == ContentDefinitionVersion.content_package_version_id,
        )
        .filter(
            ContentReleaseItem.content_release_id == project.content_release_id,
            ContentDefinitionVersion.definition_key == "test.authoring",
        )
        .one_or_none()
    )
    if existing is not None:
        return existing.id

    package_id = new_uuid7()
    package_version_id = new_uuid7()
    release_id = new_uuid7()
    definition_id = new_uuid7()
    package_key = f"test.authoring.{package_id}"
    payload = _authoring_payload()
    item_checksum = canonical_json_sha256(payload)
    manifest = {
        "package_key": package_key,
        "semantic_version": "1.0.0-test",
        "items": ["test.authoring"],
    }
    now = utc_now()
    package_version = ContentPackageVersion(
        id=package_version_id,
        content_package_id=package_id,
        semantic_version="1.0.0-test",
        runtime_constraint=">=0.1.0",
        manifest_json=manifest,
        archive_asset_version_id=None,
        checksum=canonical_json_sha256(manifest),
        status="draft",
        validated_at=None,
        published_at=None,
    )
    release = ContentRelease(
        id=release_id,
        release_key=f"{package_key}@1.0.0-test",
        name="Test authoring release",
        status="draft",
        published_at=None,
        published_by=None,
        notes="Test-only authoring fixture.",
    )
    spec = payload["spec"]
    session.add_all(
        [
            ContentPackage(
                id=package_id,
                package_key=package_key,
                name="Test authoring package",
                package_type="builtin",
                owner_scope="platform",
                status="active",
            ),
            package_version,
            release,
        ]
    )
    session.flush()
    session.add_all(
        [
            ContentPackageItemVersion(
                id=new_uuid7(),
                content_package_version_id=package_version_id,
                item_key="test.authoring",
                kind="content_definition",
                schema_id=schema_id,
                payload_json=payload,
                checksum=item_checksum,
            ),
            ContentDefinitionVersion(
                id=definition_id,
                definition_key="test.authoring",
                content_package_version_id=package_version_id,
                schema_json=build_content_json_schema(spec),
                ui_schema_json={},
                export_mapping_json={},
                validation_rules_json=build_content_validation_rules(spec),
                checksum=item_checksum,
            ),
            ContentReleaseItem(
                id=new_uuid7(),
                content_release_id=release_id,
                content_package_version_id=package_version_id,
                mount_key="test_authoring",
                priority=100,
            ),
        ]
    )
    session.flush()
    package_version.status = "published"
    package_version.validated_at = now
    package_version.published_at = now
    release.status = "published"
    release.published_at = now
    release.published_by = project.owner_principal_id
    project.content_release_id = release.id
    session.flush()
    return definition_id


def _ensure_test_authoring_workflow(session, published_version_id):
    published = session.get(WorkflowDefinitionVersion, published_version_id)
    assert published is not None
    graph = deepcopy(published.graph_json)
    node = next(item for item in graph["nodes"] if item["node_key"] == "audio.plan.generate")
    node["output_persistence"]["artifact"]["content_definition_ref"]["item_key"] = "test.authoring"
    prepare = deepcopy(
        next(item for item in graph["nodes"] if item["node_key"] == "material.scope_review")
    )
    prepare.update(
        node_key="prepare",
        title="Test-only project preparation",
        input_contract_refs=[],
        output_contract_refs=[],
        dependencies=[],
        entrypoint=True,
    )
    prepare.pop("output_persistence")
    material_entry = next(
        item for item in graph["nodes"] if item["node_key"] == "material.file_validate"
    )
    material_entry["dependencies"] = ["prepare"]
    material_entry["entrypoint"] = False
    graph["nodes"].append(prepare)
    registered = BUILTIN_WORKFLOW_REGISTRY.load(graph)
    assert registered.output_definition_index["test.authoring"].quality_requirement_mode == "none"
    checksum = canonical_json_sha256(graph)
    existing = session.scalar(
        select(WorkflowDefinitionVersion).where(WorkflowDefinitionVersion.checksum == checksum)
    )
    if existing is not None:
        return existing.id
    version = WorkflowDefinitionVersion(
        id=new_uuid7(),
        workflow_definition_id=published.workflow_definition_id,
        version_no=int(
            session.scalar(
                select(func.max(WorkflowDefinitionVersion.version_no)).where(
                    WorkflowDefinitionVersion.workflow_definition_id
                    == published.workflow_definition_id
                )
            )
            or 0
        )
        + 1,
        graph_json=graph,
        input_contract_json=dict(published.input_contract_json),
        status="published",
        checksum=checksum,
        published_at=utc_now(),
    )
    session.add(version)
    session.flush()
    return version.id


def _bind_test_workflow(session, project, workflow_version_id) -> None:
    project.workflow_definition_version_id = workflow_version_id
    current = session.scalar(
        select(AutomationPolicy)
        .where(AutomationPolicy.project_id == project.id)
        .order_by(AutomationPolicy.policy_version.desc())
        .limit(1)
    )
    assert current is not None
    if current.workflow_definition_version_id == workflow_version_id:
        return
    session.add(
        AutomationPolicy(
            id=new_uuid7(),
            organization_id=current.organization_id,
            project_id=current.project_id,
            workflow_definition_version_id=workflow_version_id,
            mode=current.mode,
            node_rules_json=list(current.node_rules_json),
            policy_version=current.policy_version + 1,
            created_at=utc_now(),
            created_by=project.owner_principal_id,
        )
    )
    session.flush()


def _authoring_payload():
    return {
        "api_version": "shanhai.edu/v1",
        "kind": "content_definition",
        "metadata": {
            "key": "test.authoring",
            "name": "Test authoring",
            "domain": "primary_math",
            "locale": "zh-CN",
        },
        "spec": {
            "definition_key": "test.authoring",
            "title": "Test authoring",
            "definition_role": "artifact",
            "fields": [
                {
                    "field_key": "title",
                    "label": "Title",
                    "type": "text",
                    "required": False,
                    "editable": True,
                    "deletable": True,
                },
                {
                    "field_key": "value",
                    "label": "Value",
                    "type": "number",
                    "required": False,
                    "editable": True,
                    "deletable": True,
                },
            ],
        },
    }
