"""Validation for declarative workflow node generation binding catalogs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

MAX_NODE_CATALOG_BYTES = 5_000_000
REGISTERED_MODEL_CAPABILITIES = frozenset(
    {
        "audio.tts.child_friendly_zh",
        "image.generate.education_16x9",
        "text.structured.audio_plan",
        "text.structured.creative_education",
        "text.structured.creative_video",
        "text.structured.image_prompt",
        "text.structured.ppt_content",
        "text.structured.ppt_design",
        "text.structured.ppt_page_design",
        "text.structured.zh_primary_math",
        "video.image_to_video.6s_30s",
        "vision.evaluate.classroom_video",
    }
)
FORBIDDEN_EXECUTOR_TOKENS = frozenset(
    {"bash", "cmd", "http", "https", "javascript", "node", "powershell", "python", "shell"}
)
TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


class NodeGenerationBindingError(ValueError):
    """Raised when a node binding catalog is unsafe or internally inconsistent."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ValidatedWorkflowNodeCatalog:
    catalog: dict[str, Any]
    canonical_json: bytes
    content_hash: str


def canonical_catalog_json(catalog: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            catalog,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NodeGenerationBindingError(
            "NODE_BINDING_VALUE_INVALID",
            "node binding catalog must contain finite JSON values",
        ) from exc


def load_workflow_node_catalog(
    catalog_path: Path,
    *,
    schema_path: Path,
) -> ValidatedWorkflowNodeCatalog:
    catalog = _load_object(catalog_path)
    schema = _load_object(schema_path)
    return validate_workflow_node_catalog(catalog, schema=schema)


def validate_workflow_node_catalog(
    catalog: dict[str, Any],
    *,
    schema: dict[str, Any],
) -> ValidatedWorkflowNodeCatalog:
    _validate_schema(catalog, schema)
    nodes = cast(list[dict[str, Any]], catalog["nodes"])
    _require_unique_node_keys(nodes)
    for node in nodes:
        _validate_node(node)
    canonical = canonical_catalog_json(catalog)
    return ValidatedWorkflowNodeCatalog(
        catalog=catalog,
        canonical_json=canonical,
        content_hash=hashlib.sha256(canonical).hexdigest(),
    )


def _load_object(path: Path) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
        if len(payload) > MAX_NODE_CATALOG_BYTES:
            raise NodeGenerationBindingError(
                "NODE_BINDING_JSON_TOO_LARGE",
                f"JSON document exceeds size limit: {path.name}",
            )
        value = json.loads(payload.decode("utf-8"))
    except NodeGenerationBindingError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NodeGenerationBindingError(
            "NODE_BINDING_JSON_INVALID",
            f"cannot read JSON object: {path.name}",
        ) from exc
    if not isinstance(value, dict):
        raise NodeGenerationBindingError(
            "NODE_BINDING_JSON_INVALID",
            f"JSON document must be an object: {path.name}",
        )
    return cast(dict[str, Any], value)


def _validate_schema(catalog: dict[str, Any], schema: dict[str, Any]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        cast(Any, validator).validate(catalog)
    except ValidationError as exc:
        path = "/".join(str(part) for part in exc.absolute_path)
        suffix = f" at {path}" if path else ""
        raise NodeGenerationBindingError(
            "NODE_BINDING_SCHEMA_INVALID",
            f"{exc.message}{suffix}",
        ) from exc


def _require_unique_node_keys(nodes: list[dict[str, Any]]) -> None:
    keys = [cast(str, node["node_key"]) for node in nodes]
    if len(keys) != len(set(keys)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_DUPLICATE_NODE_KEY",
            "node binding catalog contains duplicate node_key values",
        )


def _validate_node(node: dict[str, Any]) -> None:
    _validate_prompt_exposure(node)
    _validate_unique_strings(node, "input_contract_refs", "NODE_BINDING_CONTRACT_REF_DUPLICATE")
    _validate_unique_strings(node, "output_contract_refs", "NODE_BINDING_CONTRACT_REF_DUPLICATE")
    _validate_unique_strings(node, "validator_refs", "NODE_BINDING_VALIDATOR_REF_DUPLICATE")
    _validate_instruction_policy(cast(dict[str, Any], node["instruction_policy"]))
    _validate_context_policy(cast(dict[str, Any], node["context_policy"]))
    _validate_reference_asset_policy(cast(dict[str, Any], node["reference_asset_policy"]))
    if node["execution_kind"] == "model_generation":
        validate_model_capability(cast(str, node["model_capability"]))
        if not node["validator_refs"]:
            raise NodeGenerationBindingError(
                "NODE_BINDING_VALIDATOR_REQUIRED",
                f"model node requires a validator: {node['node_key']}",
            )
    elif node["execution_kind"] == "deterministic":
        _validate_executor(cast(str, node["executor_ref"]))
    elif not cast(dict[str, Any], node["approval_policy"])["required_before_downstream"]:
        raise NodeGenerationBindingError(
            "NODE_BINDING_HUMAN_GATE_INVALID",
            f"human gate must block downstream execution: {node['node_key']}",
        )


def _validate_prompt_exposure(node: dict[str, Any]) -> None:
    policy = cast(dict[str, Any], node["prompt_exposure_policy"])
    teacher_surface = policy["teacher_business_prompt"]
    if node["execution_kind"] == "model_generation" and teacher_surface == "not_applicable":
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROMPT_EXPOSURE_INVALID",
            f"model node must declare an editable or hidden business prompt: {node['node_key']}",
        )
    if node["execution_kind"] != "model_generation" and teacher_surface != "not_applicable":
        raise NodeGenerationBindingError(
            "NODE_BINDING_PROMPT_EXPOSURE_INVALID",
            f"non-model node cannot expose a business prompt: {node['node_key']}",
        )


def _validate_instruction_policy(policy: dict[str, Any]) -> None:
    refs = cast(list[dict[str, Any]], policy["refs"])
    identities = [
        (ref["content_key"], ref["content_kind"], ref["semantic_version"]) for ref in refs
    ]
    if len(identities) != len(set(identities)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_INSTRUCTION_REF_DUPLICATE",
            "instruction policy contains duplicate immutable content references",
        )


def _validate_context_policy(policy: dict[str, Any]) -> None:
    allowed = cast(list[str], policy["allowed_sources"])
    forbidden = cast(list[str], policy["forbidden_sources"])
    if len(allowed) != len(set(allowed)) or len(forbidden) != len(set(forbidden)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_CONTEXT_SOURCE_DUPLICATE",
            "context policy contains duplicate source values",
        )
    overlap = set(allowed) & set(forbidden)
    if overlap:
        raise NodeGenerationBindingError(
            "NODE_BINDING_CONTEXT_CONFLICT",
            f"context sources cannot be both allowed and forbidden: {sorted(overlap)}",
        )


def _validate_reference_asset_policy(policy: dict[str, Any]) -> None:
    roles = cast(list[dict[str, Any]], policy["roles"])
    keys = [cast(str, role["role_key"]) for role in roles]
    if len(keys) != len(set(keys)):
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_ROLE_DUPLICATE",
            "reference asset policy contains duplicate role_key values",
        )
    for role in roles:
        _validate_reference_role(role)
    required_roles = [role for role in roles if role["requirement"] == "required"]
    if policy["mode"] == "required" and not required_roles:
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_POLICY_INVALID",
            "required reference asset policy needs at least one required role",
        )
    if policy["mode"] == "optional" and required_roles:
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_POLICY_INVALID",
            "optional reference asset policy cannot contain required roles",
        )


def _validate_reference_role(role: dict[str, Any]) -> None:
    minimum = cast(int, role["min_items"])
    maximum = cast(int, role["max_items"])
    if maximum < minimum:
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_CARDINALITY_INVALID",
            f"reference role max_items is below min_items: {role['role_key']}",
        )
    if role["requirement"] == "required" and minimum < 1:
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_CARDINALITY_INVALID",
            f"required reference role must have min_items >= 1: {role['role_key']}",
        )
    if role["requirement"] == "optional" and minimum != 0:
        raise NodeGenerationBindingError(
            "NODE_BINDING_REFERENCE_CARDINALITY_INVALID",
            f"optional reference role must have min_items = 0: {role['role_key']}",
        )
    for field in ("media_types", "allowed_sources", "provider_exposure"):
        values = cast(list[str], role[field])
        if len(values) != len(set(values)):
            raise NodeGenerationBindingError(
                "NODE_BINDING_REFERENCE_VALUE_DUPLICATE",
                f"reference role contains duplicate {field}: {role['role_key']}",
            )


def validate_model_capability(capability: str) -> None:
    """Require a registered logical capability at the workflow contract boundary."""

    if capability not in REGISTERED_MODEL_CAPABILITIES:
        raise NodeGenerationBindingError(
            "NODE_BINDING_CAPABILITY_FORBIDDEN",
            f"model capability must be registered and provider-neutral: {capability}",
        )


def _validate_executor(executor_ref: str) -> None:
    tokens = set(TOKEN_SPLIT.split(executor_ref.lower()))
    if tokens & FORBIDDEN_EXECUTOR_TOKENS:
        raise NodeGenerationBindingError(
            "NODE_BINDING_EXECUTOR_FORBIDDEN",
            f"executor_ref must identify a registered safe executor: {executor_ref}",
        )


def _validate_unique_strings(node: dict[str, Any], field: str, code: str) -> None:
    values = cast(list[str], node[field])
    if len(values) != len(set(values)):
        raise NodeGenerationBindingError(
            code,
            f"node contains duplicate {field}: {node['node_key']}",
        )
