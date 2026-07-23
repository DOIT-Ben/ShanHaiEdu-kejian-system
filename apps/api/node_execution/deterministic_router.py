"""Published deterministic-executor routing without a business-specific queue."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.content_runtime.deterministic_port import (
    SqlAlchemyDeterministicDefinitionReader,
)
from apps.api.identity.context import ActorContext
from apps.api.ppt_runtime.materials import ASSEMBLE_EXECUTOR, EXPORT_EXECUTOR
from apps.api.ppt_runtime.service import PptRuntimeService
from apps.api.ppt_runtime.sqlalchemy import SqlAlchemyPptRuntimeTransactionFactory
from apps.api.uploads.storage import ObjectStorage
from apps.api.workflows.execution_port import SqlAlchemyWorkflowExecutionPort

from .contracts import NodeExecutionError


class DeterministicNodeExecutionResult(Protocol):
    node_run_id: UUID
    artifact_version_id: UUID


class DeterministicNodeExecutorPort(Protocol):
    def execute(
        self,
        node_run_id: UUID,
        *,
        request_id: str,
    ) -> DeterministicNodeExecutionResult: ...


class ExecutorRefReader(Protocol):
    def executor_ref(self, node_run_id: UUID) -> str: ...


class PublishedDeterministicNodeExecutor:
    def __init__(
        self,
        definitions: ExecutorRefReader,
        executors: Mapping[str, DeterministicNodeExecutorPort],
    ) -> None:
        self._definitions = definitions
        self._executors = dict(executors)

    def execute(
        self,
        node_run_id: UUID,
        *,
        request_id: str,
    ) -> DeterministicNodeExecutionResult:
        executor_ref = self._definitions.executor_ref(node_run_id)
        executor = self._executors.get(executor_ref)
        if executor is None:
            raise NodeExecutionError(
                "NODE_EXECUTION_EXECUTOR_UNSUPPORTED",
                "the published deterministic executor is unavailable",
            )
        return executor.execute(node_run_id, request_id=request_id)


class SqlAlchemyExecutorRefReader:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        actor: ActorContext,
    ) -> None:
        self._session_factory = session_factory
        self._actor = actor

    def executor_ref(self, node_run_id: UUID) -> str:
        with self._session_factory() as session:
            workflow = SqlAlchemyWorkflowExecutionPort(session, self._actor)
            return (
                SqlAlchemyDeterministicDefinitionReader(
                    session,
                    self._actor,
                    workflow,
                )
                .resolve(node_run_id)
                .executor_ref
            )


def build_deterministic_node_executor(
    session_factory: sessionmaker[Session],
    actor: ActorContext,
    storage: ObjectStorage,
    *,
    storage_bucket: str,
) -> PublishedDeterministicNodeExecutor:
    ppt = PptRuntimeService(
        SqlAlchemyPptRuntimeTransactionFactory(session_factory, actor),
        storage,
        storage_bucket=storage_bucket,
    )
    ppt_executor = cast(DeterministicNodeExecutorPort, ppt)
    return PublishedDeterministicNodeExecutor(
        SqlAlchemyExecutorRefReader(session_factory, actor),
        {
            ASSEMBLE_EXECUTOR: ppt_executor,
            EXPORT_EXECUTOR: ppt_executor,
        },
    )
