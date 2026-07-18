"""Runtime dependency probes for API and worker readiness."""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Protocol, cast

import httpx
import psycopg
from redis.asyncio import Redis
from sqlalchemy.engine import make_url

from apps.api.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DependencyStatus:
    name: str
    ready: bool
    status: str

    def as_dict(self) -> dict[str, str | bool]:
        return {"name": self.name, "ready": self.ready, "status": self.status}


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    ready: bool
    dependencies: tuple[DependencyStatus, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "ready" if self.ready else "not_ready",
            "dependencies": [dependency.as_dict() for dependency in self.dependencies],
        }


class Probe(Protocol):
    name: str

    async def check(self) -> None: ...


class ReadinessProvider(Protocol):
    async def check(self) -> ReadinessReport: ...


class AsyncRedisClient(Protocol):
    async def ping(self) -> bool: ...

    async def aclose(self) -> None: ...


class MissingConfigurationError(RuntimeError):
    pass


class MissingConfigurationProbe:
    def __init__(self, name: str) -> None:
        self.name = name

    async def check(self) -> None:
        raise MissingConfigurationError("dependency is not configured")


def psycopg_dsn(database_url: str) -> str:
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("PostgreSQL readiness requires a PostgreSQL URL")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


class PostgreSQLProbe:
    name = "postgresql"

    def __init__(self, dsn: str, timeout_seconds: float) -> None:
        self._dsn = dsn
        self._timeout_seconds = timeout_seconds

    async def check(self) -> None:
        await asyncio.to_thread(self._check_sync)

    def _check_sync(self) -> None:
        with psycopg.connect(
            psycopg_dsn(self._dsn),
            connect_timeout=max(1, math.ceil(self._timeout_seconds)),
        ) as connection:
            connection.execute("SELECT 1")


class RedisProbe:
    name = "redis"

    def __init__(self, url: str, timeout_seconds: float) -> None:
        self._url = url
        self._timeout_seconds = timeout_seconds

    async def check(self) -> None:
        client = cast(
            AsyncRedisClient,
            Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
                self._url,
                socket_connect_timeout=self._timeout_seconds,
                socket_timeout=self._timeout_seconds,
            ),
        )
        try:
            await client.ping()
        finally:
            await client.aclose()


class ObjectStorageProbe:
    name = "object_storage"

    def __init__(self, health_url: str, timeout_seconds: float) -> None:
        self._health_url = health_url
        self._timeout_seconds = timeout_seconds

    async def check(self) -> None:
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.get(self._health_url)
            response.raise_for_status()


class ReadinessService:
    def __init__(self, probes: tuple[Probe, ...]) -> None:
        self._probes = probes

    async def check(self) -> ReadinessReport:
        statuses = await asyncio.gather(*(self._check_probe(probe) for probe in self._probes))
        return ReadinessReport(
            ready=all(status.ready for status in statuses),
            dependencies=tuple(statuses),
        )

    @staticmethod
    async def _check_probe(probe: Probe) -> DependencyStatus:
        try:
            await probe.check()
        except Exception as exc:
            logger.warning(
                "dependency_readiness_failed",
                extra={"dependency": probe.name, "error_type": type(exc).__name__},
            )
            status = (
                "not_configured" if isinstance(exc, MissingConfigurationError) else "unavailable"
            )
            return DependencyStatus(name=probe.name, ready=False, status=status)
        return DependencyStatus(name=probe.name, ready=True, status="available")


def build_readiness_service(settings: Settings) -> ReadinessService:
    database_probe: Probe = (
        PostgreSQLProbe(
            settings.database_url.get_secret_value(),
            settings.dependency_timeout_seconds,
        )
        if settings.database_url
        else MissingConfigurationProbe("postgresql")
    )
    redis_probe: Probe = (
        RedisProbe(settings.redis_url.get_secret_value(), settings.dependency_timeout_seconds)
        if settings.redis_url
        else MissingConfigurationProbe("redis")
    )
    storage_probe: Probe = (
        ObjectStorageProbe(
            str(settings.object_storage_health_url),
            settings.dependency_timeout_seconds,
        )
        if settings.object_storage_health_url
        else MissingConfigurationProbe("object_storage")
    )
    return ReadinessService((database_probe, redis_probe, storage_probe))
