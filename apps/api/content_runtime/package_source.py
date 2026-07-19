"""Trusted loader for the repository's built-in courseware release source."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from workflow.content_package import canonical_json_sha256, validate_content_package
from workflow.node_generation_binding import load_workflow_node_catalog


class ContentPublicationConflict(ValueError):
    """Raised when immutable publication content or identities disagree."""


@dataclass(frozen=True, slots=True)
class BuiltinCoursewareReleaseSource:
    manifest: dict[str, Any]
    items: dict[str, dict[str, Any]]
    manifest_entries: dict[str, dict[str, Any]]
    workflow_catalog: dict[str, Any]
    package_checksum: str
    workflow_checksum: str

    @property
    def package_key(self) -> str:
        return cast(str, self.manifest["package_key"])

    @property
    def package_name(self) -> str:
        return cast(str, self.manifest["name"])

    @property
    def semantic_version(self) -> str:
        return cast(str, self.manifest["semantic_version"])

    @property
    def runtime_constraint(self) -> str:
        return cast(str, self.manifest["runtime_constraint"])

    @property
    def release_key(self) -> str:
        return f"{self.package_key}@{self.semantic_version}"

    @property
    def workflow_key(self) -> str:
        return cast(str, self.workflow_catalog["workflow_key"])

    @property
    def content_definition_count(self) -> int:
        return sum(
            entry["kind"] == "content_definition" for entry in self.manifest_entries.values()
        )


def load_builtin_courseware_release(root: Path) -> BuiltinCoursewareReleaseSource:
    """Load and cross-check the repository's one authoritative built-in release source."""

    contracts_root = root / "contracts"
    package = validate_content_package(
        contracts_root / "fixtures/primary-math-courseware-package",
        contracts_root=contracts_root,
    )
    catalog = load_workflow_node_catalog(
        contracts_root
        / "fixtures/workflow-node-generation-bindings/primary-math-courseware.json",
        schema_path=contracts_root / "workflow-node-generation-binding.schema.json",
    )
    manifest_entries = {
        cast(str, entry["item_key"]): cast(dict[str, Any], entry)
        for entry in cast(list[dict[str, Any]], package.manifest["items"])
    }
    entrypoints = set(cast(list[str], package.manifest["entrypoints"]))
    model_template_refs = {
        cast(str, node["generation_template_ref"]["item_key"])
        for node in cast(list[dict[str, Any]], catalog.catalog["nodes"])
        if node["execution_kind"] == "model_generation"
    }
    if package.manifest["semantic_version"] != catalog.catalog["semantic_version"]:
        raise ContentPublicationConflict("package and workflow catalog versions differ")
    if entrypoints != model_template_refs:
        raise ContentPublicationConflict("package entrypoints and model node bindings differ")
    return BuiltinCoursewareReleaseSource(
        manifest=package.manifest,
        items=dict(package.items),
        manifest_entries=manifest_entries,
        workflow_catalog=catalog.catalog,
        package_checksum=canonical_json_sha256(package.manifest),
        workflow_checksum=catalog.content_hash,
    )
