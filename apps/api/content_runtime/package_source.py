"""Trusted loader for the repository's built-in courseware release source."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from workflow.content_package import canonical_json_sha256, validate_content_package
from workflow.node_generation_binding import load_workflow_node_catalog
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY


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
    def workflow_input_contract(self) -> dict[str, str]:
        return {
            "package_key": self.package_key,
            "package_semantic_version": self.semantic_version,
            "package_checksum": self.package_checksum,
            "workflow_checksum": self.workflow_checksum,
        }

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
        contracts_root / "fixtures/workflow-node-generation-bindings/primary-math-courseware.json",
        schema_path=contracts_root / "workflow-node-generation-binding.schema.json",
    )
    # Publication and execution must validate the exact same graph shape.  The
    # binding validator checks package-local semantics; the runtime registry
    # additionally proves that the persisted graph is executable without
    # falling back to a legacy catalog or hard-coded contract list.
    BUILTIN_WORKFLOW_REGISTRY.load(catalog.catalog)
    manifest_entries = {
        cast(str, entry["item_key"]): entry
        for entry in cast(list[dict[str, Any]], package.manifest["items"])
    }
    _validate_catalog_content_definitions(catalog.catalog, package.items, manifest_entries)
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


def _validate_catalog_content_definitions(
    catalog: dict[str, Any],
    items: dict[str, dict[str, Any]],
    manifest_entries: dict[str, dict[str, Any]],
) -> None:
    for node in cast(list[dict[str, Any]], catalog["nodes"]):
        if node["execution_kind"] != "model_generation":
            continue
        template_key = cast(str, node["generation_template_ref"]["item_key"])
        template = items.get(template_key)
        if template is None or manifest_entries[template_key]["kind"] != "generation_template":
            raise ContentPublicationConflict(
                f"generation template is missing from the published package: {template_key}"
            )
        spec = cast(dict[str, Any], template.get("spec", {}))
        output_ref = spec.get("output_definition_ref")
        artifact_ref = node["output_persistence"]["artifact"]["content_definition_ref"]
        if output_ref != artifact_ref:
            raise ContentPublicationConflict(
                f"artifact output definition disagrees with generation template: {node['node_key']}"
            )
        output_key = cast(str, artifact_ref["item_key"])
        if (
            output_key not in items
            or manifest_entries[output_key]["kind"] != "content_definition"
        ):
            raise ContentPublicationConflict(
                f"content definition is missing from the published package: {output_key}"
            )
