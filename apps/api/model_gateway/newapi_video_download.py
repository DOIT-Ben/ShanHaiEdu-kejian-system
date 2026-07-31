"""Bounded NewAPI video download and result-store persistence."""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    GeneratedFileFact,
    ModelGatewayError,
    VideoResultScope,
)
from apps.api.model_gateway.video_store import (
    ScopedVideoResultStore,
    StoredVideoFile,
    VideoResultStore,
)


async def download_completed_video(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: dict[str, str],
    max_download_bytes: int,
    store: VideoResultStore,
    result_scope: VideoResultScope | None,
    provider_name: str,
    task_id: str,
    raise_for_error: Callable[[httpx.Response], None],
) -> tuple[GeneratedFileFact, str | None]:
    temporary_path: Path | None = None
    try:
        temporary_path, media_type, sha256, size_bytes, request_id = await _download_to_temp(
            client,
            url=url,
            headers=headers,
            max_download_bytes=max_download_bytes,
            raise_for_error=raise_for_error,
        )
        stored = await _persist_result(
            store,
            source=temporary_path,
            media_type=media_type,
            result_scope=result_scope,
            provider_name=provider_name,
            task_id=task_id,
        )
        return _generated_file_fact(
            stored,
            sha256=sha256,
            size_bytes=size_bytes,
            mime_type=media_type,
        ), request_id
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


async def _download_to_temp(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: dict[str, str],
    max_download_bytes: int,
    raise_for_error: Callable[[httpx.Response], None],
) -> tuple[Path, str, str, int, str | None]:
    try:
        async with client.stream("GET", url, headers=headers) as response:
            raise_for_error(response)
            media_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if media_type != "video/mp4" or _content_length_exceeds_limit(
                response.headers.get("Content-Length"), max_download_bytes
            ):
                raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
            path, sha256, size_bytes = await _write_stream(response, max_download_bytes)
            return path, media_type, sha256, size_bytes, _request_id(response)
    except httpx.TimeoutException as exc:
        raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True) from exc
    except httpx.RequestError as exc:
        raise ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True) from exc


async def _write_stream(response: httpx.Response, maximum: int) -> tuple[Path, str, int]:
    digest = hashlib.sha256()
    size_bytes = 0
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="shanhaiedu-video-", suffix=".mp4", delete=False
        ) as file:
            path = Path(file.name)
            async for chunk in response.aiter_bytes():
                size_bytes += len(chunk)
                if size_bytes > maximum:
                    raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
                digest.update(chunk)
                file.write(chunk)
        if size_bytes == 0:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
        return path, digest.hexdigest(), size_bytes
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        raise


async def _persist_result(
    store: VideoResultStore,
    *,
    source: Path,
    media_type: str,
    result_scope: VideoResultScope | None,
    provider_name: str,
    task_id: str,
) -> StoredVideoFile:
    if result_scope is None:
        return await _persist_smoke(
            store,
            key=f"model-smoke/video/{task_id}.mp4",
            source=source,
            media_type=media_type,
        )
    if not isinstance(store, ScopedVideoResultStore):
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    try:
        return await asyncio.to_thread(
            store.stage,
            source=source,
            media_type=media_type,
            scope=result_scope,
            provider_name=provider_name,
            provider_task_id=task_id,
        )
    except OSError as exc:
        raise ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True) from exc


async def _persist_smoke(
    store: VideoResultStore,
    *,
    key: str,
    source: Path,
    media_type: str,
) -> StoredVideoFile:
    try:
        return await asyncio.to_thread(
            store.persist,
            key=key,
            source=source,
            media_type=media_type,
        )
    except OSError as exc:
        raise ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True) from exc


def _generated_file_fact(
    stored: StoredVideoFile,
    *,
    sha256: str,
    size_bytes: int,
    mime_type: str,
) -> GeneratedFileFact:
    if stored.size_bytes != size_bytes or stored.mime_type != mime_type or stored.sha256 != sha256:
        raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
    return GeneratedFileFact(
        storage_key=stored.storage_key,
        sha256=sha256,
        size_bytes=size_bytes,
        mime_type=mime_type,
    )


def _content_length_exceeds_limit(value: str | None, maximum: int) -> bool:
    if value is None:
        return False
    try:
        return int(value) > maximum
    except ValueError:
        return True


def _request_id(response: httpx.Response) -> str | None:
    value = response.headers.get("X-Request-ID")
    if value is None or not value.strip() or len(value) > 255:
        return None
    return value
