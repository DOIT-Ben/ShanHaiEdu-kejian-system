"""SQLAlchemy transaction owner for deterministic PPT node execution."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.deterministic_port import SqlAlchemyDeterministicArtifactPort
from apps.api.assets.ppt_runtime_contracts import (
    PptBackgroundFact,
    PublishedPptxObject,
)
from apps.api.assets.ppt_runtime_port import (
    SqlAlchemyPptAssetPort,
)
from apps.api.content_runtime.deterministic_port import (
    DeterministicNodeDefinition,
    SqlAlchemyDeterministicDefinitionReader,
)
from apps.api.identity.context import ActorContext
from apps.api.model_gateway.deterministic_port import SqlAlchemyDeterministicAttemptPort
from apps.api.ppt_rendering import ManifestPage
from apps.api.runtime_boundary.ports import ArtifactContextVersion, WorkflowExecutionContext
from apps.api.workflows.execution_port import SqlAlchemyWorkflowExecutionPort
from apps.api.workflows.execution_values import execution_snapshot_hash
from workflow.node_state import NodeStatus

from .contracts import (
    PptRenderProduct,
    PptRuntimeResult,
    PptRuntimeTransaction,
    PptRuntimeTransactionFactory,
    PreparedPptRuntime,
)
from .failure import terminalize_prepare_failure
from .materials import (
    ASSEMBLE_EXECUTOR,
    EXPORT_EXECUTOR,
    SNAPSHOT_KIND,
    build_prepared,
    definition_fact,
    error,
    execution_snapshot,
    mapping,
    require_commit_identity,
    require_supported_definition,
    required_input,
    sha256,
)
from .outputs import artifact_content, output_bytes, require_render_product
from .page_recovery import build_page_recovery_details, parse_page_recovery_details


class SqlAlchemyPptRuntimeTransactionFactory(PptRuntimeTransactionFactory):
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        actor: ActorContext,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._actor = actor
        self._fault_injector = fault_injector or _ignore_fault

    @contextmanager
    def begin(self) -> Generator[PptRuntimeTransaction]:
        session = self._session_factory()
        try:
            with session.begin():
                yield SqlAlchemyPptRuntimeTransaction(
                    session,
                    self._actor,
                    fault_injector=self._fault_injector,
                )
        finally:
            session.close()


class SqlAlchemyPptRuntimeTransaction(PptRuntimeTransaction):
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        fault_injector: Callable[[str], None],
    ) -> None:
        self._session = session
        self._actor = actor
        self._workflow = SqlAlchemyWorkflowExecutionPort(session, actor)
        self._definitions = SqlAlchemyDeterministicDefinitionReader(
            session,
            actor,
            self._workflow,
        )
        self._artifacts = SqlAlchemyDeterministicArtifactPort(session, actor)
        self._assets = SqlAlchemyPptAssetPort(session, actor)
        self._attempts = SqlAlchemyDeterministicAttemptPort(session, actor)
        self._fault_injector = fault_injector

    def prepare(
        self,
        node_run_id: UUID,
        request_id: str,
    ) -> PreparedPptRuntime | PptRuntimeResult:
        execution = self._workflow.require_context(node_run_id, for_update=True)
        committed = self._workflow.committed_artifact(node_run_id)
        if committed is not None:
            return self._committed_result(execution, committed, request_id)
        if execution.status == NodeStatus.CANCEL_REQUESTED.value:
            raise error(
                "PPT_RUNTIME_CANCEL_REQUESTED",
                "the deterministic PPT node was cancelled before execution",
            )
        definition = self._definitions.resolve(node_run_id)
        require_supported_definition(definition, execution)
        inputs, backgrounds, request_hash = self._frozen_inputs(
            definition,
            execution,
            request_id,
        )
        recovered_pages = (
            parse_page_recovery_details(
                self._attempts.recoverable_failure_details(
                    execution,
                    request_hash=request_hash,
                ),
                backgrounds=backgrounds,
                request_hash=request_hash,
            )
            if definition.executor_ref == ASSEMBLE_EXECUTOR
            else ()
        )
        owner_token = str(uuid4())
        self._workflow.claim_execution_owner(node_run_id, owner_token)
        self._workflow.start(node_run_id)
        attempt = self._attempts.start(
            execution,
            owner_token=owner_token,
            request_hash=request_hash,
            capability=definition.executor_ref,
        )
        return build_prepared(
            definition,
            execution,
            request_id,
            request_hash,
            owner_token,
            attempt,
            inputs,
            backgrounds,
            recovered_pages,
        )

    def complete(
        self,
        prepared: PreparedPptRuntime,
        product: PptRenderProduct,
        published: PublishedPptxObject | None,
        *,
        latency_ms: int,
    ) -> PptRuntimeResult:
        current = self._require_completion_context(prepared, product, published)
        evidence = self._attempts.complete(
            current,
            prepared.attempt,
            latency_ms=latency_ms,
            input_bytes=sum(item.size_bytes for item in prepared.backgrounds),
            output_bytes=output_bytes(product),
        )
        self._fault_injector("after_attempt")
        file_fact = None
        if published is not None:
            file_fact = self._assets.persist_pptx(
                current,
                published,
                page_count=len(product.manifest.pages),
                implementation_version=product.manifest.implementation_version,
            )
        self._fault_injector("after_file_asset")
        content = artifact_content(prepared, product.manifest, file_fact)
        artifact = self._artifacts.persist(
            prepared.definition,
            current,
            prepared.upstream_artifacts,
            content,
            request_id=prepared.request_id,
        )
        self._fault_injector("after_artifact")
        self._workflow.release_execution_owner(current.node_run_id, prepared.owner_token)
        self._workflow.complete(current.node_run_id, artifact.artifact_version_id)
        if prepared.definition.executor_ref == ASSEMBLE_EXECUTOR:
            self._artifacts.approve_system_output(
                artifact.artifact_version_id,
                request_id=prepared.request_id,
            )
            self._workflow.transition(current.node_run_id, NodeStatus.APPROVED)
        self._fault_injector("after_terminal")
        return PptRuntimeResult(
            node_run_id=current.node_run_id,
            artifact_version_id=artifact.artifact_version_id,
            file_asset_version_id=(file_fact.file_asset_version_id if file_fact else None),
            attempt_id=evidence.attempt_id,
            usage_id=evidence.usage_id,
        )

    def _committed_result(
        self,
        execution: WorkflowExecutionContext,
        committed_version_id: UUID,
        request_id: str,
    ) -> PptRuntimeResult:
        self._workflow.require_execution_request(execution.node_run_id, request_id)
        artifact = self._artifacts.result_for_version(committed_version_id)
        evidence = self._attempts.succeeded(execution)
        return PptRuntimeResult(
            node_run_id=execution.node_run_id,
            artifact_version_id=artifact.artifact_version_id,
            file_asset_version_id=artifact.file_asset_version_id,
            attempt_id=evidence.attempt_id,
            usage_id=evidence.usage_id,
        )

    def _frozen_inputs(
        self,
        definition: DeterministicNodeDefinition,
        execution: WorkflowExecutionContext,
        request_id: str,
    ) -> tuple[
        dict[str, ArtifactContextVersion],
        tuple[PptBackgroundFact, ...],
        str,
    ]:
        frozen = self._workflow.find_frozen_execution_snapshot(execution.node_run_id, request_id)
        if frozen is not None:
            inputs, backgrounds = self._load_frozen(definition, execution, frozen)
            return inputs, backgrounds, execution_snapshot_hash(frozen)
        inputs, backgrounds = self._fresh_inputs(definition, execution)
        snapshot = execution_snapshot(definition, inputs, backgrounds)
        self._workflow.freeze_execution(
            execution,
            request_id=request_id,
            snapshot=snapshot,
        )
        frozen = {**snapshot, "request_id": request_id}
        return inputs, backgrounds, execution_snapshot_hash(frozen)

    def _require_completion_context(
        self,
        prepared: PreparedPptRuntime,
        product: PptRenderProduct,
        published: PublishedPptxObject | None,
    ) -> WorkflowExecutionContext:
        current = self._workflow.require_context(prepared.execution.node_run_id, for_update=True)
        if current.status == NodeStatus.CANCEL_REQUESTED.value:
            raise error(
                "PPT_RUNTIME_CANCEL_REQUESTED",
                "the deterministic PPT node was cancelled before commit",
            )
        require_commit_identity(prepared, current)
        if not self._workflow.owns_execution_owner(current.node_run_id, prepared.owner_token):
            raise error("PPT_RUNTIME_OWNER_LOST", "the PPT node execution lease was lost")
        self._artifacts.verify_inputs(current, prepared.upstream_artifacts)
        self._assets.verify_backgrounds(
            current,
            page_spec_version_id=prepared.page_spec_version_id,
            page_spec_content=prepared.page_spec_content,
            expected=prepared.backgrounds,
        )
        require_render_product(prepared, product, published)
        return current

    def terminalize_failure(
        self,
        prepared: PreparedPptRuntime,
        *,
        code: str,
        cancelled: bool,
        latency_ms: int,
        completed_pages: tuple[ManifestPage, ...],
    ) -> None:
        if not self._workflow.owns_execution_owner(
            prepared.execution.node_run_id,
            prepared.owner_token,
        ):
            return
        if not self._attempts.fail_if_owned(
            prepared.execution,
            prepared.attempt,
            code=code,
            cancelled=cancelled,
            latency_ms=latency_ms,
            recovery_details=(
                build_page_recovery_details(
                    completed_pages,
                    request_hash=prepared.request_hash,
                )
                if completed_pages and not cancelled
                else None
            ),
        ):
            return
        self._workflow.release_execution_owner(
            prepared.execution.node_run_id,
            prepared.owner_token,
        )
        self._workflow.terminalize(
            prepared.execution.node_run_id,
            code=code,
            cancelled=cancelled,
        )

    def fail_prepare(self, node_run_id: UUID, *, code: str) -> None:
        terminalize_prepare_failure(
            self._session,
            self._actor,
            self._workflow,
            node_run_id,
            code=code,
        )

    def _fresh_inputs(
        self,
        definition: DeterministicNodeDefinition,
        execution: WorkflowExecutionContext,
    ) -> tuple[dict[str, ArtifactContextVersion], tuple[PptBackgroundFact, ...]]:
        inputs = self._artifacts.select_inputs(execution, definition.input_contract_refs)
        page_specs = required_input(inputs, "artifact:ppt_page_specs")
        if definition.executor_ref == EXPORT_EXECUTOR:
            required_input(inputs, "artifact:ppt_page_previews")
        backgrounds = self._assets.resolve_backgrounds(
            execution,
            page_spec_version_id=page_specs.artifact_version_id,
            page_spec_content=page_specs.content,
            for_update=False,
        )
        return inputs, backgrounds

    def _load_frozen(
        self,
        definition: DeterministicNodeDefinition,
        execution: WorkflowExecutionContext,
        frozen: Mapping[str, Any],
    ) -> tuple[dict[str, ArtifactContextVersion], tuple[PptBackgroundFact, ...]]:
        if frozen.get("kind") != SNAPSHOT_KIND or frozen.get("definition") != definition_fact(
            definition
        ):
            raise error(
                "PPT_RUNTIME_FROZEN_INPUT_INVALID",
                "the frozen PPT definition differs from the fixed release",
            )
        raw_artifacts = frozen.get("artifacts")
        if not isinstance(raw_artifacts, Mapping):
            raise error("PPT_RUNTIME_FROZEN_INPUT_INVALID", "frozen artifacts are invalid")
        refs: dict[str, UUID] = {}
        expected_hashes: dict[str, str] = {}
        for ref, value in cast(Mapping[object, object], raw_artifacts).items():
            if type(ref) is not str or not isinstance(value, Mapping):
                raise error("PPT_RUNTIME_FROZEN_INPUT_INVALID", "frozen artifacts are invalid")
            item = cast(Mapping[object, object], value)
            try:
                refs[ref] = UUID(str(item.get("version_id")))
            except ValueError as exc:
                raise error(
                    "PPT_RUNTIME_FROZEN_INPUT_INVALID",
                    "a frozen artifact version is invalid",
                ) from exc
            expected_hashes[ref] = sha256(item.get("content_hash"))
        inputs = self._artifacts.load_inputs(execution, refs)
        if any(value.content_hash != expected_hashes[ref] for ref, value in inputs.items()):
            raise error(
                "PPT_RUNTIME_FROZEN_INPUT_INVALID",
                "a frozen artifact hash differs from its immutable version",
            )
        raw_backgrounds = frozen.get("backgrounds")
        if not isinstance(raw_backgrounds, Sequence) or isinstance(
            raw_backgrounds,
            (str, bytes, bytearray),
        ):
            raise error("PPT_RUNTIME_FROZEN_INPUT_INVALID", "frozen backgrounds are invalid")
        backgrounds = tuple(
            PptBackgroundFact.from_snapshot(mapping(value))
            for value in cast(Sequence[object], raw_backgrounds)
        )
        required_input(inputs, "artifact:ppt_page_specs")
        if definition.executor_ref == EXPORT_EXECUTOR:
            required_input(inputs, "artifact:ppt_page_previews")
        return inputs, backgrounds


def _ignore_fault(_: str) -> None:
    return None
