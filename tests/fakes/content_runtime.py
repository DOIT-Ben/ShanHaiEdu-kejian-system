from __future__ import annotations

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
from apps.api.database import utc_now
from apps.api.ids import new_uuid7
from apps.api.projects.models import Project
from workflow.content_package import canonical_json_sha256


def ensure_test_authoring_definition(session, project_id):
    project = session.get(Project, project_id)
    assert project is not None
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
                schema_id="https://shanhaiedu.local/contracts/content-definition.schema.json",
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
