"""PostgreSQL-backed idempotent command execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.ids import new_uuid7
from apps.api.reliability.models import IdempotencyRecord


def canonical_request_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CommandResult:
    status_code: int
    body: dict[str, object]
    resource_type: str | None = None
    resource_id: UUID | None = None
    replayed: bool = False


class IdempotencyService:
    def __init__(
        self,
        session: Session,
        organization_id: UUID,
        *,
        ttl_seconds: int,
    ) -> None:
        self._session = session
        self._organization_id = organization_id
        self._ttl_seconds = ttl_seconds

    def execute(
        self,
        *,
        scope: str,
        key: str,
        payload: Mapping[str, Any],
        command: Callable[[], CommandResult],
    ) -> CommandResult:
        request_hash = canonical_request_hash(payload)
        self._lock_key(scope, key)
        existing = self._find(scope, key)
        replay = self._replay(existing, request_hash, scope)
        if replay is not None:
            return replay

        result = command()
        now = utc_now()
        record = IdempotencyRecord(
            id=new_uuid7(),
            organization_id=self._organization_id,
            scope=scope,
            idempotency_key=key,
            request_hash=request_hash,
            response_status=result.status_code,
            response_body_json=result.body,
            resource_type=result.resource_type,
            resource_id=result.resource_id,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
            created_at=now,
        )
        self._session.add(record)
        self._session.flush()
        return replace(result, replayed=False)

    def lookup(
        self,
        *,
        scope: str,
        key: str,
        payload: Mapping[str, Any],
    ) -> CommandResult | None:
        request_hash = canonical_request_hash(payload)
        self._lock_key(scope, key)
        return self._replay(self._find(scope, key), request_hash, scope)

    def _find(self, scope: str, key: str) -> IdempotencyRecord | None:
        existing = self._session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.organization_id == self._organization_id,
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == key,
            )
        )
        now = utc_now()
        if existing is not None and existing.expires_at <= now:
            self._session.delete(existing)
            self._session.flush()
            existing = None
        return existing

    @staticmethod
    def _replay(
        existing: IdempotencyRecord | None,
        request_hash: str,
        scope: str,
    ) -> CommandResult | None:
        if existing is None:
            return None
        if existing.request_hash != request_hash:
            raise ApiError(
                status_code=409,
                code="IDEMPOTENCY_CONFLICT",
                message="The idempotency key was already used for a different request.",
                details={"scope": scope},
            )
        return CommandResult(
            status_code=existing.response_status,
            body=existing.response_body_json,
            resource_type=existing.resource_type,
            resource_id=existing.resource_id,
            replayed=True,
        )

    def _lock_key(self, scope: str, key: str) -> None:
        digest = hashlib.sha256(f"{self._organization_id}:{scope}:{key}".encode()).digest()
        lock_id = int.from_bytes(digest[:8], byteorder="big", signed=True)
        self._session.execute(select(func.pg_advisory_xact_lock(lock_id)))
