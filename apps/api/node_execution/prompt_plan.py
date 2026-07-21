"""Compile one release-bound model request without business-specific branches."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from apps.api.model_gateway.contracts import (
    ModelAuditContext,
    ModelCapability,
    TextModelRequest,
)
from apps.api.runtime_boundary.ports import RuntimeNodeDefinition, WorkflowExecutionContext
from workflow.prompt_runtime import (
    AssembledContext,
    CompiledPrompt,
    ContextBinding,
    ContextItem,
    PromptRuntimeError,
    PromptSection,
    assemble_context,
    compile_prompt,
)

from .boundaries import validate_execution_boundary

_PLATFORM_SAFETY = "Enforce tenant isolation, platform safety, and the published output contract."
_PROVIDER_FORMAT = "Return exactly one JSON object and no commentary."


class NodePromptPlanError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class CompiledNodePrompt:
    context: AssembledContext
    prompt: CompiledPrompt
    request: TextModelRequest
    audit_context: ModelAuditContext


@dataclass(frozen=True, slots=True)
class _PromptContract:
    prompt_key: str
    capability: ModelCapability
    sections: tuple[PromptSection, ...]
    bindings: tuple[ContextBinding, ...]
    allowed_sources: frozenset[str]
    edit_max_chars: int


def compile_node_prompt(
    *,
    definition: RuntimeNodeDefinition,
    execution: WorkflowExecutionContext,
    prompt_template: Mapping[str, Any],
    output_schema: dict[str, object],
    context_items: tuple[ContextItem, ...],
    request_id: str,
    user_id: UUID | None,
) -> CompiledNodePrompt:
    validate_execution_boundary(definition, execution)
    contract = _resolve_contract(definition, prompt_template)
    values = _group_context_items(context_items, contract.allowed_sources)
    try:
        context = assemble_context(
            contract.bindings,
            values,
            allowed_sources=contract.allowed_sources,
        )
        prompt = compile_prompt(
            template_key=contract.prompt_key,
            template_version=str(definition.content_release_id),
            platform_safety=_PLATFORM_SAFETY,
            sections=contract.sections,
            context=context,
            output_schema=output_schema,
            provider_format=_PROVIDER_FORMAT,
            user_edit_mode="replace_editable_layer",
            user_edit_max_chars=contract.edit_max_chars,
        )
    except PromptRuntimeError as exc:
        raise NodePromptPlanError(exc.code, str(exc)) from exc
    request = TextModelRequest(
        capability=contract.capability,
        request_id=request_id,
        prompt=prompt.compiled_prompt,
        max_output_tokens=128_000,
        temperature=0,
    )
    audit = ModelAuditContext(
        organization_id=execution.organization_id,
        user_id=user_id,
        project_id=execution.project_id,
        node_run_id=execution.node_run_id,
        generation_job_id=None,
    )
    return CompiledNodePrompt(context=context, prompt=prompt, request=request, audit_context=audit)


def _resolve_contract(
    definition: RuntimeNodeDefinition,
    prompt_template: Mapping[str, Any],
) -> _PromptContract:
    binding = definition.node_binding
    generation_spec = _required_mapping(definition.generation_template.get("spec"))
    prompt_spec = _required_mapping(prompt_template.get("spec"))
    prompt_ref = _required_mapping(generation_spec.get("prompt_template_ref"))
    output_ref = _required_mapping(generation_spec.get("output_definition_ref"))
    policy = _required_mapping(binding.get("context_policy"))
    prompt_key = prompt_ref.get("item_key")
    capability_value = generation_spec.get("model_capability")
    if not _contract_identities_match(
        definition,
        binding,
        prompt_spec,
        prompt_key,
        output_ref,
        capability_value,
    ):
        raise NodePromptPlanError(
            "NODE_EXECUTION_PROMPT_CONTRACT_MISMATCH",
            "published generation and prompt contracts disagree",
        )
    try:
        capability = ModelCapability(cast(str, capability_value))
        sections = _prompt_sections(prompt_spec.get("sections"))
        bindings = _context_bindings(prompt_spec.get("context_bindings"))
        allowed_sources = _allowed_sources(policy)
        edit_max_chars = _edit_max_chars(prompt_spec.get("user_edit_policy"))
    except (TypeError, ValueError, KeyError) as exc:
        raise NodePromptPlanError(
            "NODE_EXECUTION_PROMPT_CONTRACT_INVALID",
            "published prompt contract is invalid",
        ) from exc
    if {item.source for item in bindings} - allowed_sources:
        raise NodePromptPlanError(
            "NODE_EXECUTION_CONTEXT_POLICY_MISMATCH",
            "prompt bindings exceed the published context policy",
        )
    return _PromptContract(
        prompt_key=cast(str, prompt_key),
        capability=capability,
        sections=sections,
        bindings=bindings,
        allowed_sources=allowed_sources,
        edit_max_chars=edit_max_chars,
    )


def _contract_identities_match(
    definition: RuntimeNodeDefinition,
    binding: Mapping[str, Any],
    prompt_spec: Mapping[str, Any],
    prompt_key: object,
    output_ref: Mapping[str, Any],
    capability: object,
) -> bool:
    return bool(
        type(prompt_key) is str
        and prompt_spec.get("template_key") == prompt_key
        and prompt_spec.get("model_capability") == capability
        and binding.get("model_capability") == capability
        and output_ref.get("item_key") == definition.content_definition_item_key
        and _required_mapping(prompt_spec.get("output_definition_ref")).get("item_key")
        == definition.content_definition_item_key
    )


def _prompt_sections(value: object) -> tuple[PromptSection, ...]:
    items = _required_sequence(value)
    return tuple(
        PromptSection(
            section_key=_required_text(item.get("section_key")),
            layer=_required_text(item.get("layer")),
            content=_required_text(item.get("content")),
            editable=_required_bool(item.get("editable")),
            visible_to_teacher=_required_bool(item.get("visible_to_teacher")),
        )
        for item in (_required_mapping(raw) for raw in items)
    )


def _context_bindings(value: object) -> tuple[ContextBinding, ...]:
    items = _required_sequence(value)
    return tuple(
        ContextBinding(
            binding_key=_required_text(item.get("binding_key")),
            source=_required_text(item.get("source")),
            required=_required_bool(item.get("required")),
            exposure=cast(Any, _required_text(item.get("exposure"))),
            max_items=_required_int(item.get("max_items")),
            max_bytes=_required_int(item.get("max_bytes")),
        )
        for item in (_required_mapping(raw) for raw in items)
    )


def _allowed_sources(policy: Mapping[str, Any]) -> frozenset[str]:
    if policy.get("mode") != "declared":
        raise ValueError("context policy is not a declared allowlist")
    allowed = frozenset(
        _required_text(value) for value in _required_sequence(policy.get("allowed_sources"))
    )
    forbidden = frozenset(
        _required_text(value) for value in _required_sequence(policy.get("forbidden_sources"))
    )
    if allowed & forbidden:
        raise ValueError("context policy allowlist and denylist overlap")
    return allowed


def _edit_max_chars(value: object) -> int:
    policy = _required_mapping(value)
    if policy.get("mode") != "replace_editable_layer":
        raise ValueError("prompt edit policy is unsupported")
    return _required_int(policy.get("max_chars"))


def _group_context_items(
    items: tuple[ContextItem, ...],
    allowed_sources: frozenset[str],
) -> dict[str, tuple[ContextItem, ...]]:
    if {item.source for item in items} - allowed_sources:
        raise NodePromptPlanError(
            "NODE_EXECUTION_CONTEXT_POLICY_MISMATCH",
            "runtime context exceeds the published context policy",
        )
    return {
        source: tuple(item for item in items if item.source == source)
        for source in sorted({item.source for item in items})
    }


def _required_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("mapping is required")
    return cast(Mapping[str, Any], value)


def _required_sequence(value: object) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("sequence is required")
    return tuple(cast(Sequence[object], value))


def _required_text(value: object) -> str:
    if type(value) is not str or not value:
        raise TypeError("text is required")
    return value


def _required_bool(value: object) -> bool:
    if type(value) is not bool:
        raise TypeError("boolean is required")
    return value


def _required_int(value: object) -> int:
    if type(value) is not int or value < 1:
        raise TypeError("positive integer is required")
    return value
