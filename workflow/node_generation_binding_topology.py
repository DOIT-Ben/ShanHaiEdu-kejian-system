"""Topology and cross-node contract checks for generation bindings."""

from __future__ import annotations

from typing import Any, cast

from workflow.node_generation_binding_common import NodeGenerationBindingError


def validate_topology(nodes: list[dict[str, Any]]) -> None:
    node_by_key = {cast(str, node["node_key"]): node for node in nodes}
    for node in nodes:
        _validate_node_dependencies(node, node_by_key)
    _validate_acyclic_dependencies(node_by_key)


def _validate_node_dependencies(
    node: dict[str, Any], node_by_key: dict[str, dict[str, Any]]
) -> None:
    key = cast(str, node["node_key"])
    dependencies = cast(list[str], node["dependencies"])
    if len(dependencies) != len(set(dependencies)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_DEPENDENCY_DUPLICATE",
            f"node contains duplicate dependencies: {key}",
        )
    if bool(node["entrypoint"]) != (not dependencies):
        raise NodeGenerationBindingError(
            "NODE_BINDING_ENTRYPOINT_INVALID",
            f"entrypoint does not match dependencies: {key}",
        )
    for dependency in dependencies:
        dependency_node = node_by_key.get(dependency)
        if dependency_node is None:
            raise NodeGenerationBindingError(
                "NODE_BINDING_DEPENDENCY_MISSING",
                f"node has missing dependency: {key} -> {dependency}",
            )
        if dependency_node["execution_scope"] != node["execution_scope"]:
            raise NodeGenerationBindingError(
                "NODE_BINDING_DEPENDENCY_SCOPE_INVALID",
                f"dependency crosses execution scope: {key} -> {dependency}",
            )
        if dependency_node["branch_key"] != node["branch_key"]:
            raise NodeGenerationBindingError(
                "NODE_BINDING_DEPENDENCY_BRANCH_INVALID",
                f"dependency crosses branch: {key} -> {dependency}",
            )


def _validate_acyclic_dependencies(node_by_key: dict[str, dict[str, Any]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visited:
            return
        if key in visiting:
            raise NodeGenerationBindingError(
                "NODE_BINDING_DEPENDENCY_CYCLE",
                "workflow node dependencies contain a cycle",
            )
        visiting.add(key)
        for dependency in cast(list[str], node_by_key[key]["dependencies"]):
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in node_by_key:
        visit(key)


def validate_contract_refs(catalog: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    external = set(cast(list[str], catalog["external_input_contract_refs"]))
    producers = _index_contract_producers(nodes)
    produced = set(producers)
    collisions = external & produced
    if collisions:
        raise NodeGenerationBindingError(
            "NODE_BINDING_EXTERNAL_CONTRACT_COLLISION",
            f"external inputs collide with published outputs: {sorted(collisions)}",
        )
    for node in nodes:
        _validate_node_contract_refs(node, external, producers)


def _index_contract_producers(
    nodes: list[dict[str, Any]],
) -> dict[str, list[tuple[str, str, str]]]:
    producers: dict[str, list[tuple[str, str, str]]] = {}
    for node in nodes:
        for output_ref in cast(list[str], node["output_contract_refs"]):
            producers.setdefault(output_ref, []).append(
                (
                    cast(str, node["execution_scope"]),
                    cast(str, node["branch_key"]),
                    cast(str, node["node_key"]),
                )
            )
    return producers


def _validate_node_contract_refs(
    node: dict[str, Any],
    external: set[str],
    producers: dict[str, list[tuple[str, str, str]]],
) -> None:
    inputs = set(cast(list[str], node["input_contract_refs"]))
    missing = inputs - external - set(producers)
    if missing:
        raise NodeGenerationBindingError(
            "NODE_BINDING_CONTRACT_REF_UNRESOLVED",
            f"node contains unresolved input contracts: {node['node_key']}: {sorted(missing)}",
        )
    group = (cast(str, node["execution_scope"]), cast(str, node["branch_key"]))
    for input_ref in inputs - external:
        candidates = producers.get(input_ref, [])
        same_group = [candidate for candidate in candidates if candidate[:2] == group]
        if not same_group and len(candidates) > 1:
            raise NodeGenerationBindingError(
                "NODE_BINDING_INPUT_PRODUCER_AMBIGUOUS",
                f"node has an ambiguous cross-branch input: {node['node_key']}: {input_ref}",
            )


def validate_model_artifact_relations(nodes: list[dict[str, Any]]) -> None:
    producers: dict[tuple[str, str, str], str] = {}
    for node in nodes:
        if node["execution_kind"] != "model_generation":
            continue
        group = (cast(str, node["execution_scope"]), cast(str, node["branch_key"]))
        for output_ref in cast(list[str], node["output_contract_refs"]):
            producers[(*group, output_ref)] = cast(str, node["node_key"])

    for node in nodes:
        if node["execution_kind"] != "model_generation":
            continue
        _validate_model_artifact_relation_sources(node, producers)


def _validate_model_artifact_relation_sources(
    node: dict[str, Any], producers: dict[tuple[str, str, str], str]
) -> None:
    group = (cast(str, node["execution_scope"]), cast(str, node["branch_key"]))
    required = {
        input_ref
        for input_ref in cast(list[str], node["input_contract_refs"])
        if producers.get((*group, input_ref)) not in {None, node["node_key"]}
    }
    persistence = cast(dict[str, Any], node["output_persistence"])
    artifact = cast(dict[str, Any], persistence["artifact"])
    declared = {
        relation["source_binding"] for relation in cast(list[dict[str, Any]], artifact["relations"])
    }
    missing = required - declared
    if missing:
        raise NodeGenerationBindingError(
            "NODE_BINDING_RELATION_SOURCE_MISSING",
            f"model node is missing Artifact relations: {node['node_key']}: {sorted(missing)}",
        )
