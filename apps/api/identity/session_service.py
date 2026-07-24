"""Persistent teacher sessions for the controlled R1 runtime."""

from __future__ import annotations

import hmac
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import AuthenticatedIdentity
from apps.api.identity.models import (
    Organization,
    OrganizationMember,
    Principal,
    Session,
    SessionLoginThrottle,
    User,
)
from apps.api.ids import new_uuid7
from apps.api.settings import Settings


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    session_id: UUID
    user_id: UUID
    organization_id: UUID
    principal_id: UUID
    display_name: str
    organization_name: str
    organization_role: str
    expires_at: datetime
    csrf_token: str

    @property
    def identity(self) -> AuthenticatedIdentity:
        return AuthenticatedIdentity(
            user_id=self.user_id,
            organization_id=self.organization_id,
        )


class DatabaseSessionService:
    """Creates and verifies opaque sessions without persisting browser secrets."""

    def __init__(self, factory: sessionmaker[OrmSession], settings: Settings) -> None:
        access_code = settings.session_access_code
        csrf_secret = settings.session_csrf_secret
        principal_id = settings.session_teacher_principal_id
        if access_code is None or csrf_secret is None or principal_id is None:
            raise ValueError("complete session configuration is required")
        self._factory = factory
        self._secret = csrf_secret.get_secret_value().encode("utf-8")
        self._access_code_digest = self._digest(
            "access-code",
            access_code.get_secret_value(),
        )
        self._principal_id = principal_id
        self._allowed_origins = frozenset(settings.session_allowed_origins)
        self._ttl = timedelta(seconds=settings.session_ttl_seconds)
        self._max_failures = settings.session_login_max_failures
        self._failure_window = timedelta(seconds=settings.session_login_window_seconds)
        self._trusted_proxy_hosts = tuple(settings.session_trusted_proxy_hosts)

    async def authenticate(self, session_token: str) -> AuthenticatedIdentity | None:
        snapshot = await run_in_threadpool(self.resolve_snapshot, session_token)
        return snapshot.identity if snapshot is not None else None

    def create_session(
        self,
        *,
        access_code: str,
        existing_token: str | None,
        source_ip: str,
    ) -> tuple[str, SessionSnapshot]:
        now = utc_now()
        source_hash = self._digest("login-source", source_ip)
        invalid_code = False
        created: tuple[str, SessionSnapshot] | None = None
        with self._factory() as database, database.begin():
            throttle = self._lock_login_source(database, source_hash)
            if self._is_limited(throttle, now):
                raise ApiError(
                    status_code=429,
                    code="LOGIN_RATE_LIMITED",
                    message="Too many failed login attempts. Try again later.",
                    retryable=True,
                )

            candidate_digest = self._digest("access-code", access_code)
            if not hmac.compare_digest(candidate_digest, self._access_code_digest):
                self._record_failed_login(database, throttle, source_hash, now)
                invalid_code = True
            else:
                if throttle is not None:
                    database.delete(throttle)
                identity = self._load_configured_identity(database)
                rotated_from = self._lock_active_session(database, existing_token, now)
                if rotated_from is not None:
                    rotated_from.revoked_at = now
                raw_token = token_urlsafe(48)
                persisted = Session(
                    id=new_uuid7(),
                    token_hash=self._token_hash(raw_token),
                    user_id=identity.user.id,
                    organization_id=identity.organization.id,
                    principal_id=identity.principal.id,
                    csrf_nonce=token_urlsafe(32),
                    created_at=now,
                    expires_at=now + self._ttl,
                    last_seen_at=now,
                    rotated_from_id=rotated_from.id if rotated_from is not None else None,
                )
                identity.user.last_login_at = now
                database.add(persisted)
                database.flush()
                created = (raw_token, self._snapshot(persisted, identity))

        if invalid_code:
            raise ApiError(
                status_code=401,
                code="AUTHENTICATION_FAILED",
                message="The supplied credential is not valid.",
            )
        if created is None:
            raise RuntimeError("session creation did not produce a session")
        return created

    def resolve_snapshot(self, session_token: str) -> SessionSnapshot | None:
        now = utc_now()
        with self._factory() as database:
            persisted = self._find_active_session(database, session_token, now)
            if persisted is None:
                return None
            identity = self._load_session_identity(database, persisted)
            if identity is None:
                return None
            return self._snapshot(persisted, identity)

    def require_snapshot(self, session_token: str | None) -> SessionSnapshot:
        snapshot = self.resolve_snapshot(session_token) if session_token else None
        if snapshot is None:
            raise authentication_required()
        return snapshot

    def revoke(self, session_token: str | None) -> None:
        if not session_token:
            raise authentication_required()
        now = utc_now()
        with self._factory() as database, database.begin():
            persisted = self._lock_active_session(database, session_token, now)
            if persisted is None:
                raise authentication_required()
            persisted.revoked_at = now

    def require_origin(self, origin: str | None) -> None:
        if origin is None or origin not in self._allowed_origins:
            raise ApiError(
                status_code=403,
                code="ORIGIN_FORBIDDEN",
                message="The request origin is not allowed.",
            )

    @staticmethod
    def require_csrf(snapshot: SessionSnapshot, supplied_token: str | None) -> None:
        if supplied_token is None or not hmac.compare_digest(
            snapshot.csrf_token,
            supplied_token,
        ):
            raise ApiError(
                status_code=403,
                code="CSRF_VALIDATION_FAILED",
                message="The CSRF token is missing or invalid.",
            )

    def source_ip(self, direct_host: str | None, forwarded_for: str | None) -> str:
        direct = self._canonical_ip(direct_host) or "unknown"
        if not self._is_trusted_proxy(direct) or not forwarded_for:
            return direct
        for forwarded_host in reversed(forwarded_for.split(",")):
            candidate = self._canonical_ip(forwarded_host.strip())
            if candidate is None:
                return direct
            if not self._is_trusted_proxy(candidate):
                return candidate
        return direct

    def _find_active_session(
        self,
        database: OrmSession,
        raw_token: str | None,
        now: datetime,
        *,
        for_update: bool = False,
    ) -> Session | None:
        if not raw_token:
            return None
        statement = select(Session).where(Session.token_hash == self._token_hash(raw_token))
        if for_update:
            statement = statement.with_for_update()
        persisted = database.scalar(statement)
        if persisted is None or persisted.revoked_at is not None:
            return None
        if persisted.expires_at <= now:
            return None
        return persisted

    def _lock_active_session(
        self,
        database: OrmSession,
        raw_token: str | None,
        now: datetime,
    ) -> Session | None:
        return self._find_active_session(database, raw_token, now, for_update=True)

    def _load_configured_identity(self, database: OrmSession) -> _IdentityRow:
        row = self._load_identity(database, self._principal_id)
        if row is None:
            raise ApiError(
                status_code=503,
                code="AUTHENTICATION_UNAVAILABLE",
                message="The configured teacher identity is unavailable.",
                retryable=True,
            )
        return row

    def _load_session_identity(
        self,
        database: OrmSession,
        persisted: Session,
    ) -> _IdentityRow | None:
        row = self._load_identity(database, persisted.principal_id)
        if row is None:
            return None
        if row.user.id != persisted.user_id or row.organization.id != persisted.organization_id:
            return None
        return row

    @staticmethod
    def _load_identity(database: OrmSession, principal_id: UUID) -> _IdentityRow | None:
        statement = (
            select(Principal, User, Organization, OrganizationMember)
            .join(User, User.id == Principal.user_id)
            .join(Organization, Organization.id == Principal.organization_id)
            .join(
                OrganizationMember,
                (OrganizationMember.user_id == User.id)
                & (OrganizationMember.organization_id == Organization.id),
            )
            .where(Principal.id == principal_id)
        )
        result = database.execute(statement).one_or_none()
        if result is None:
            return None
        principal, user, organization, membership = result
        if principal.principal_type != "user" or any(
            status != "active"
            for status in (
                principal.status,
                user.status,
                organization.status,
                membership.status,
            )
        ):
            return None
        return _IdentityRow(
            principal=principal,
            user=user,
            organization=organization,
            membership=membership,
        )

    def _snapshot(self, persisted: Session, identity: _IdentityRow) -> SessionSnapshot:
        payload = f"{persisted.id}:{persisted.csrf_nonce}"
        return SessionSnapshot(
            session_id=persisted.id,
            user_id=identity.user.id,
            organization_id=identity.organization.id,
            principal_id=identity.principal.id,
            display_name=identity.principal.display_name,
            organization_name=identity.organization.name,
            organization_role=identity.membership.role,
            expires_at=persisted.expires_at,
            csrf_token=self._digest("csrf", payload),
        )

    def _lock_login_source(
        self,
        database: OrmSession,
        source_hash: str,
    ) -> SessionLoginThrottle | None:
        lock_key = int.from_bytes(bytes.fromhex(source_hash[:16]), "big", signed=True)
        database.execute(select(func.pg_advisory_xact_lock(lock_key)))
        return database.scalar(
            select(SessionLoginThrottle)
            .where(SessionLoginThrottle.source_hash == source_hash)
            .with_for_update()
        )

    def _is_limited(
        self,
        throttle: SessionLoginThrottle | None,
        now: datetime,
    ) -> bool:
        return bool(
            throttle is not None
            and now - throttle.window_started_at < self._failure_window
            and throttle.failure_count >= self._max_failures
        )

    def _record_failed_login(
        self,
        database: OrmSession,
        throttle: SessionLoginThrottle | None,
        source_hash: str,
        now: datetime,
    ) -> None:
        if throttle is None:
            database.add(
                SessionLoginThrottle(
                    source_hash=source_hash,
                    window_started_at=now,
                    failure_count=1,
                    updated_at=now,
                )
            )
            return
        if now - throttle.window_started_at >= self._failure_window:
            throttle.window_started_at = now
            throttle.failure_count = 1
        else:
            throttle.failure_count += 1
        throttle.updated_at = now

    def _token_hash(self, raw_token: str) -> str:
        return self._digest("session-token", raw_token)

    def _digest(self, purpose: str, value: str) -> str:
        return hmac.new(
            self._secret,
            f"{purpose}\0{value}".encode(),
            sha256,
        ).hexdigest()

    def _is_trusted_proxy(self, host: str) -> bool:
        address = self._canonical_ip(host)
        if address is None:
            return False
        parsed_address = ipaddress.ip_address(address)
        for configured in self._trusted_proxy_hosts:
            try:
                if parsed_address in ipaddress.ip_network(configured, strict=False):
                    return True
            except ValueError:
                if configured == host:
                    return True
        return False

    @staticmethod
    def _canonical_ip(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            return None


@dataclass(frozen=True, slots=True)
class _IdentityRow:
    principal: Principal
    user: User
    organization: Organization
    membership: OrganizationMember


def authentication_required() -> ApiError:
    return ApiError(
        status_code=401,
        code="AUTHENTICATION_REQUIRED",
        message="Authentication is required for this request.",
    )
