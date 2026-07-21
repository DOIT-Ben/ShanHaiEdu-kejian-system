"""Workflow-owned persistent lease for one node execution worker."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import database_wall_clock
from apps.api.workflows.models import NodeExecutionLease
from apps.api.workflows.repository import WorkflowRuntimeRepository

_EXECUTION_LEASE_SECONDS = 300


class NodeExecutionLeaseError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SqlAlchemyNodeExecutionLeasePort:
    def __init__(self, session: Session, repository: WorkflowRuntimeRepository) -> None:
        self._session = session
        self._repository = repository

    def claim(self, node_run_id: UUID, owner_token: str) -> None:
        if self._repository.get_node(node_run_id, for_update=True) is None:
            raise NodeExecutionLeaseError("NODE_EXECUTION_NOT_FOUND", "node run not found")
        now = database_wall_clock(self._session)
        lease = self._locked(node_run_id)
        if lease is not None and lease.lease_expires_at > now:
            raise NodeExecutionLeaseError(
                "NODE_EXECUTION_IN_FLIGHT",
                "another worker already owns the frozen node execution",
            )
        expires_at = now + timedelta(seconds=_EXECUTION_LEASE_SECONDS)
        if lease is None:
            self._session.add(
                NodeExecutionLease(
                    node_run_id=node_run_id,
                    owner_token=owner_token,
                    lease_expires_at=expires_at,
                )
            )
        else:
            lease.owner_token = owner_token
            lease.lease_expires_at = expires_at
        self._session.flush()

    def owns(self, node_run_id: UUID, owner_token: str) -> bool:
        lease = self._locked(node_run_id)
        return bool(lease is not None and lease.owner_token == owner_token)

    def release(self, node_run_id: UUID, owner_token: str) -> None:
        lease = self._locked(node_run_id)
        if lease is None:
            raise NodeExecutionLeaseError("NODE_EXECUTION_NOT_FOUND", "node lease not found")
        if lease.owner_token != owner_token:
            raise NodeExecutionLeaseError(
                "NODE_EXECUTION_OWNER_LOST",
                "the worker no longer owns the node execution",
            )
        self._session.delete(lease)
        self._session.flush()

    def discard(self, node_run_id: UUID) -> None:
        lease = self._locked(node_run_id)
        if lease is not None:
            self._session.delete(lease)
            self._session.flush()

    def _locked(self, node_run_id: UUID) -> NodeExecutionLease | None:
        return self._session.scalar(
            select(NodeExecutionLease)
            .where(NodeExecutionLease.node_run_id == node_run_id)
            .with_for_update()
        )
