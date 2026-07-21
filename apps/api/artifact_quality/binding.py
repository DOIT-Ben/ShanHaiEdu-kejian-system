"""Published quality-report binding resolution without node-key conditionals."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import cast

from apps.api.artifact_quality.contracts import ValidatorRef
from workflow.definition import WorkflowNodeDefinition
from workflow.registry import RegisteredWorkflow


class QualityReportBindingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class QualityReportBinding:
    source_input_ref: str
    validator_refs: tuple[ValidatorRef, ...]
    validator_set_hash: str


def resolve_quality_report_binding(
    registered: RegisteredWorkflow,
    node_key: str,
) -> QualityReportBinding:
    node = registered.node_by_key.get(node_key)
    if node is None:
        raise _invalid("the validate node is not declared by the fixed workflow")
    persistence = node.binding.get("quality_report_persistence")
    if not isinstance(persistence, Mapping):
        raise _invalid("the fixed node has no quality-report persistence binding")
    values = cast(Mapping[str, object], persistence)
    source_input_ref = values.get("source_input_ref")
    raw_refs = values.get("validator_refs")
    if type(source_input_ref) is not str or not isinstance(raw_refs, (list, tuple)):
        raise _invalid("the fixed quality-report binding is invalid")
    refs = tuple(
        _validator_ref(registered, node, raw)
        for raw in cast(list[object] | tuple[object, ...], raw_refs)
    )
    canonical = canonical_validator_refs(refs)
    return QualityReportBinding(
        source_input_ref=source_input_ref,
        validator_refs=canonical,
        validator_set_hash=validator_set_hash(canonical),
    )


def canonical_validator_refs(refs: tuple[ValidatorRef, ...]) -> tuple[ValidatorRef, ...]:
    canonical = tuple(
        sorted(
            refs,
            key=lambda item: (
                item.key,
                item.semantic_version,
                item.implementation_digest,
            ),
        )
    )
    if not canonical or len(set(canonical)) != len(canonical):
        raise _invalid("the fixed validator set is empty or duplicated")
    return canonical


def validator_set_payload(refs: tuple[ValidatorRef, ...]) -> list[dict[str, str]]:
    return [asdict(item) for item in canonical_validator_refs(refs)]


def validator_set_hash(refs: tuple[ValidatorRef, ...]) -> str:
    payload = json.dumps(
        validator_set_payload(refs),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validator_ref(
    registered: RegisteredWorkflow,
    node: WorkflowNodeDefinition,
    raw: object,
) -> ValidatorRef:
    if not isinstance(raw, Mapping):
        raise _invalid(f"quality validator ref is invalid for {node.node_key}")
    values = cast(Mapping[str, object], raw)
    key = values.get("key")
    version = values.get("semantic_version")
    digest = values.get("implementation_digest")
    if type(key) is not str or type(version) is not str or type(digest) is not str:
        raise _invalid(f"quality validator ref is invalid for {node.node_key}")
    descriptor = registered.validator_descriptor_index.get((key, version))
    if descriptor is None or descriptor.get("implementation_digest") != digest:
        raise _invalid(f"quality validator digest is not fixed for {node.node_key}")
    return ValidatorRef(key=key, semantic_version=version, implementation_digest=digest)


def _invalid(message: str) -> QualityReportBindingError:
    return QualityReportBindingError("QUALITY_REPORT_BINDING_INVALID", message)
