"""PostgreSQL-authorized cleanup for staged and unbound video objects."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.assets.video_port import VideoAssetCleanupPort
from apps.api.database import (
    build_engine,
    build_session_factory,
    database_wall_clock,
)
from apps.api.jobs.video_port import VideoCleanupJobFact, VideoJobCleanupPort
from apps.api.model_gateway.contracts import VideoResultScope
from apps.api.model_gateway.video_cleanup_port import VideoCleanupAttemptPort
from apps.api.model_registry import register_models
from apps.api.settings import get_settings
from apps.api.uploads.storage import (
    ObjectMetadata,
    ObjectNotFoundError,
    ObjectStorage,
    ObjectStorageError,
    build_object_storage,
)

logger = logging.getLogger(__name__)

_STAGING_PREFIX = "staging/video-results"
_FINAL_PREFIX = "assets/video-results"
_STAGING_TTL_SECONDS = 86_400
_UNBOUND_FINAL_TTL_SECONDS = 604_800
_TERMINAL_STAGING_STATUSES = {"succeeded", "failed", "cancelled"}
_DELETABLE_FINAL_STATUSES = {"failed", "cancelled"}


@dataclass(frozen=True, slots=True)
class _VideoObjectIdentity:
    kind: Literal["staging", "final"]
    scope: VideoResultScope
    sha256: str | None


@dataclass(frozen=True, slots=True)
class VideoCleanupResult:
    scanned_count: int
    candidate_count: int
    deleted_count: int


@dataclass(frozen=True, slots=True)
class _CleanupDecision:
    eligible: bool
    reason: str | None = None
    job_status: str | None = None


class VideoObjectCleanupCoordinator:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: ObjectStorage,
        *,
        bucket: str,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._bucket = bucket

    def cleanup(
        self,
        *,
        now: datetime | None = None,
        dry_run: bool = True,
        limit: int = 100,
    ) -> VideoCleanupResult:
        if not 1 <= limit <= 100:
            raise ValueError("video cleanup limit must be between 1 and 100")
        checked_at = self._database_now() if now is None else _aware(now)
        objects = sorted(
            [
                *self._storage.list_objects(
                    bucket=self._bucket,
                    prefix=f"{_STAGING_PREFIX}/",
                    limit=limit,
                ),
                *self._storage.list_objects(
                    bucket=self._bucket,
                    prefix=f"{_FINAL_PREFIX}/",
                    limit=limit,
                ),
            ],
            key=_metadata_age_order,
        )[:limit]
        candidates = tuple(
            (metadata, identity)
            for metadata in objects
            if (identity := _parse_identity(metadata.key)) is not None
            and _expired(metadata, identity, now=checked_at)
            and self._eligible(identity, metadata.key, now=checked_at, for_update=False)
        )
        deleted_count = 0
        if not dry_run:
            for metadata, identity in candidates:
                if self._delete_if_still_eligible(metadata, identity, now=checked_at):
                    deleted_count += 1
        result = VideoCleanupResult(
            scanned_count=len(objects),
            candidate_count=len(candidates),
            deleted_count=deleted_count,
        )
        logger.info(
            "video_object_cleanup_completed",
            extra={
                "dry_run": dry_run,
                "scanned_count": result.scanned_count,
                "candidate_count": result.candidate_count,
                "deleted_count": result.deleted_count,
            },
        )
        return result

    def _database_now(self) -> datetime:
        with self._session_factory() as session:
            return database_wall_clock(session)

    def _eligible(
        self,
        identity: _VideoObjectIdentity,
        key: str,
        *,
        now: datetime,
        for_update: bool,
        session: Session | None = None,
    ) -> bool:
        if session is not None:
            decision = _database_decision(
                session,
                identity,
                bucket=self._bucket,
                key=key,
                now=now,
                for_update=for_update,
            )
        else:
            with self._session_factory() as read_session:
                decision = _database_decision(
                    read_session,
                    identity,
                    bucket=self._bucket,
                    key=key,
                    now=now,
                    for_update=for_update,
                )
        if not decision.eligible:
            _log_retained(identity, key, decision)
        return decision.eligible

    def _delete_if_still_eligible(
        self,
        listed: ObjectMetadata,
        identity: _VideoObjectIdentity,
        *,
        now: datetime,
    ) -> bool:
        try:
            current = self._storage.stat(bucket=self._bucket, key=listed.key)
        except ObjectNotFoundError:
            return False
        if current.key != listed.key or not _expired(current, identity, now=now):
            return False
        with self._session_factory() as session, session.begin():
            if not self._eligible(
                identity,
                listed.key,
                now=now,
                for_update=True,
                session=session,
            ):
                return False
            self._storage.delete(bucket=self._bucket, key=listed.key)
            try:
                self._storage.stat(bucket=self._bucket, key=listed.key)
            except ObjectNotFoundError:
                return True
            except ObjectStorageError as exc:
                logger.warning(
                    "video_object_cleanup_confirmation_failed",
                    extra={
                        "scope_hash": _scope_hash(identity.scope),
                        "key_hash": _key_hash(listed.key),
                        "error_type": type(exc).__name__,
                    },
                )
                return False
            logger.warning(
                "video_object_cleanup_delete_not_confirmed",
                extra={
                    "scope_hash": _scope_hash(identity.scope),
                    "key_hash": _key_hash(listed.key),
                },
            )
            return False


def run_video_object_cleanup(*, execute: bool = False, limit: int = 100) -> int:
    """Inspect or delete expired video objects using PostgreSQL authorization."""

    settings = get_settings()
    if settings.database_url is None:
        return 1
    storage = build_object_storage(settings)
    if storage is None:
        return 1
    register_models()
    engine = build_engine(settings.database_url.get_secret_value())
    try:
        result = VideoObjectCleanupCoordinator(
            build_session_factory(engine),
            storage,
            bucket=settings.object_storage_bucket,
        ).cleanup(dry_run=not execute, limit=limit)
    finally:
        engine.dispose()
    print(
        json.dumps(
            {
                "conclusion": "passed",
                "dry_run": not execute,
                "scanned_count": result.scanned_count,
                "candidate_count": result.candidate_count,
                "deleted_count": result.deleted_count,
            },
            ensure_ascii=True,
        )
    )
    return 0


def _database_decision(
    session: Session,
    identity: _VideoObjectIdentity,
    *,
    bucket: str,
    key: str,
    now: datetime,
    for_update: bool,
) -> _CleanupDecision:
    job = VideoJobCleanupPort(session).fact(
        identity.scope.generation_job_id,
        for_update=for_update,
    )
    if job is None:
        return _CleanupDecision(False, "job_missing")
    if not _scope_matches(job, identity.scope):
        return _CleanupDecision(False, "scope_mismatch", job.status)
    if VideoCleanupAttemptPort(session).active_exists(
        identity.scope.generation_job_id,
        identity.scope.organization_id,
        now=now,
    ):
        return _CleanupDecision(False, "active_attempt", job.status)
    if identity.kind == "staging":
        if job.status in _TERMINAL_STAGING_STATUSES or (
            job.lease_expires_at is not None and _aware(job.lease_expires_at) <= now
        ):
            return _CleanupDecision(True, job_status=job.status)
        return _CleanupDecision(False, "job_not_terminal_or_lease_active", job.status)
    if job.status not in _DELETABLE_FINAL_STATUSES:
        return _CleanupDecision(False, "job_status_retained", job.status)
    if identity.sha256 is None:
        return _CleanupDecision(False, "invalid_final_identity", job.status)
    bound_sha256 = VideoAssetCleanupPort(session).binding_sha256(bucket=bucket, key=key)
    if bound_sha256 is None:
        return _CleanupDecision(True, job_status=job.status)
    if bound_sha256 != identity.sha256:
        logger.warning(
            "video_object_cleanup_binding_conflict",
            extra={
                "scope_hash": _scope_hash(identity.scope),
                "key_hash": _key_hash(key),
            },
        )
        return _CleanupDecision(False, "binding_conflict", job.status)
    return _CleanupDecision(False, "file_asset_bound", job.status)


def _log_retained(
    identity: _VideoObjectIdentity,
    key: str,
    decision: _CleanupDecision,
) -> None:
    logger.warning(
        "video_object_cleanup_retained",
        extra={
            "reason": decision.reason,
            "job_status": decision.job_status,
            "scope_hash": _scope_hash(identity.scope),
            "key_hash": _key_hash(key),
        },
    )


def _scope_matches(job: VideoCleanupJobFact, scope: VideoResultScope) -> bool:
    return (
        job.organization_id == scope.organization_id
        and job.project_id == scope.project_id
        and job.lesson_unit_id == scope.lesson_unit_id
        and job.job_type == "video.golden_slice"
    )


def _parse_identity(key: str) -> _VideoObjectIdentity | None:
    parts = key.split("/")
    if len(parts) != 7 or parts[1] != "video-results" or not parts[6].endswith(".mp4"):
        return None
    if parts[0] == "staging":
        kind: Literal["staging", "final"] = "staging"
        expected_length = 32
    elif parts[0] == "assets":
        kind = "final"
        expected_length = 64
    else:
        return None
    leaf = parts[6][:-4]
    if len(leaf) != expected_length or any(
        character not in "0123456789abcdef" for character in leaf
    ):
        return None
    try:
        scope_ids = tuple(UUID(value) for value in parts[2:6])
    except ValueError:
        return None
    if any(str(value) != raw for value, raw in zip(scope_ids, parts[2:6], strict=True)):
        return None
    scope = VideoResultScope(
        organization_id=scope_ids[0],
        project_id=scope_ids[1],
        lesson_unit_id=scope_ids[2],
        generation_job_id=scope_ids[3],
    )
    return _VideoObjectIdentity(
        kind=kind,
        scope=scope,
        sha256=leaf if kind == "final" else None,
    )


def _expired(metadata: ObjectMetadata, identity: _VideoObjectIdentity, *, now: datetime) -> bool:
    modified = metadata.last_modified
    if modified is None:
        return False
    ttl = _STAGING_TTL_SECONDS if identity.kind == "staging" else _UNBOUND_FINAL_TTL_SECONDS
    return _aware(modified).timestamp() <= now.timestamp() - ttl


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _scope_hash(scope: VideoResultScope) -> str:
    value = (
        f"{scope.organization_id}/{scope.project_id}/{scope.lesson_unit_id}/"
        f"{scope.generation_job_id}"
    )
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _metadata_age_order(metadata: ObjectMetadata) -> tuple[float, str]:
    modified = metadata.last_modified
    if modified is None:
        return (float("inf"), metadata.key)
    return (_aware(modified).timestamp(), metadata.key)
