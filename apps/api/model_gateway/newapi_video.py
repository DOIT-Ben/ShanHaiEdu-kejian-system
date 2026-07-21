"""NewAPI video-grok adapter for the platform-owned media gateway.

Wire contract: https://newapi.doitbenai.cloud/openapi.json
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol, cast
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    GeneratedFileFact,
    ModelGatewayError,
    ModelUsage,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
    VideoProviderResult,
)
from apps.api.model_gateway.openai_compatible import map_provider_error


class NewApiVideoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1, max_length=160)
    api_key: SecretStr
    timeout_seconds: float = Field(gt=0, le=600)
    max_download_bytes: int = Field(gt=0, le=1_073_741_824)


@dataclass(frozen=True, slots=True)
class StoredVideoFile:
    storage_key: str
    sha256: str
    size_bytes: int
    mime_type: str


class VideoResultStore(Protocol):
    def persist(
        self,
        *,
        key: str,
        source: Path,
        media_type: str,
    ) -> StoredVideoFile: ...


class LocalVideoSmokeStore:
    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root.resolve()

    def persist(
        self,
        *,
        key: str,
        source: Path,
        media_type: str,
    ) -> StoredVideoFile:
        if not source.is_file() or media_type != "video/mp4":
            raise OSError("video smoke output source is invalid")
        destination = self.path_for(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        payload = destination.read_bytes()
        if not payload:
            destination.unlink(missing_ok=True)
            raise OSError("video smoke output is empty")
        return StoredVideoFile(
            storage_key=key,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            mime_type=media_type,
        )

    def path_for(self, key: str) -> Path:
        relative = PurePosixPath(key)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise OSError("video smoke output key is unsafe")
        destination = (self._output_root / Path(*relative.parts)).resolve()
        try:
            destination.relative_to(self._output_root)
        except ValueError as exc:
            raise OSError("video smoke output key escapes the output root") from exc
        return destination


class _GatewayMediaTask(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    model: str = Field(min_length=1, max_length=160)
    status: Literal["queued", "processing", "completed", "failed"]
    hasOutput: bool = False


class NewApiVideoProvider:
    def __init__(
        self,
        config: NewApiVideoConfig,
        *,
        store: VideoResultStore,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            headers={
                "Authorization": f"Bearer {config.api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
        )

    @property
    def provider_name(self) -> str:
        return self._config.provider_name

    @property
    def model_name(self) -> str:
        return self._config.model

    async def submit(self, request: VideoModelRequest) -> VideoProviderResult:
        if request.references:
            raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
        try:
            response = await self._client.post(
                self._url("videos"),
                json={
                    "model": self._config.model,
                    "prompt": request.prompt,
                    "duration": request.duration_seconds,
                },
                headers=self._headers(**{"Idempotency-Key": _idempotency_key(request.request_id)}),
            )
        except httpx.TimeoutException as exc:
            raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True) from exc
        except httpx.RequestError as exc:
            raise ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True) from exc
        if response.status_code == 409:
            return VideoProviderResult(
                status=VideoOperationStatus.SUBMISSION_UNKNOWN,
                provider_request_id=_request_id(response),
                provider_task_id=None,
                actual_model=self._config.model,
                usage=ModelUsage(),
            )
        task = _validated_task(response)
        return await self._result_for_task(
            task,
            provider_request_id=_request_id(response),
            submitted=True,
        )

    async def poll(self, request: VideoPollRequest) -> VideoProviderResult:
        response = await self._get_task(request.provider_task_id)
        task = _validated_task(response)
        return await self._result_for_task(
            task,
            provider_request_id=_request_id(response),
            submitted=False,
        )

    async def cancel(self, request: VideoPollRequest) -> VideoProviderResult:
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get_task(self, task_id: str) -> httpx.Response:
        try:
            return await self._client.get(
                self._url(f"videos/{task_id}"),
                headers=self._headers(),
            )
        except httpx.TimeoutException as exc:
            raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True) from exc
        except httpx.RequestError as exc:
            raise ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True) from exc

    async def _result_for_task(
        self,
        task: _GatewayMediaTask,
        *,
        provider_request_id: str | None,
        submitted: bool,
    ) -> VideoProviderResult:
        task_id = str(task.id)
        if task.status in {"queued", "processing"}:
            return VideoProviderResult(
                status=(
                    VideoOperationStatus.SUBMITTED if submitted else VideoOperationStatus.POLLING
                ),
                provider_request_id=provider_request_id,
                provider_task_id=task_id,
                actual_model=task.model,
                usage=ModelUsage(),
            )
        if task.status == "failed":
            return VideoProviderResult(
                status=VideoOperationStatus.FAILED,
                provider_request_id=provider_request_id,
                provider_task_id=task_id,
                actual_model=task.model,
                usage=ModelUsage(),
            )
        file, content_request_id = await self._download_completed_video(task_id)
        return VideoProviderResult(
            status=VideoOperationStatus.SUCCEEDED,
            provider_request_id=content_request_id or provider_request_id,
            provider_task_id=task_id,
            actual_model=task.model,
            files=[file],
            usage=ModelUsage(),
        )

    async def _download_completed_video(self, task_id: str) -> tuple[GeneratedFileFact, str | None]:
        temporary_path: Path | None = None
        try:
            try:
                async with self._client.stream(
                    "GET",
                    self._url(f"videos/{task_id}/content"),
                    headers=self._headers(),
                ) as response:
                    _raise_for_error(response)
                    media_type = (
                        response.headers.get("Content-Type", "").split(";", maxsplit=1)[0].lower()
                    )
                    content_length = response.headers.get("Content-Length")
                    if media_type != "video/mp4" or _content_length_exceeds_limit(
                        content_length,
                        self._config.max_download_bytes,
                    ):
                        raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
                    digest = hashlib.sha256()
                    size_bytes = 0
                    with tempfile.NamedTemporaryFile(
                        prefix="shanhaiedu-video-", suffix=".mp4", delete=False
                    ) as file:
                        temporary_path = Path(file.name)
                        async for chunk in response.aiter_bytes():
                            size_bytes += len(chunk)
                            if size_bytes > self._config.max_download_bytes:
                                raise ModelGatewayError(
                                    GatewayErrorCode.INVALID_RESPONSE,
                                    retryable=False,
                                )
                            digest.update(chunk)
                            file.write(chunk)
            except httpx.TimeoutException as exc:
                raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True) from exc
            except httpx.RequestError as exc:
                raise ModelGatewayError(
                    GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True
                ) from exc
            if size_bytes == 0:
                raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
            key = f"model-smoke/video/{task_id}.mp4"
            stored = await _persist_video(
                self._store,
                key=key,
                source=temporary_path,
                media_type=media_type,
            )
            file = _generated_file_fact(
                stored,
                key=key,
                sha256=digest.hexdigest(),
                size_bytes=size_bytes,
                mime_type=media_type,
            )
            return file, _request_id(response)
        finally:
            _delete_temporary_file(temporary_path)

    def _url(self, path: str) -> str:
        return f"{self._config.base_url.rstrip('/')}/{path}"

    def _headers(self, **extra: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
            **extra,
        }


def _idempotency_key(request_id: str) -> str:
    return f"video-smoke-{hashlib.sha256(request_id.encode('utf-8')).hexdigest()}"


def _validated_task(response: httpx.Response) -> _GatewayMediaTask:
    _raise_for_error(response)
    try:
        return _GatewayMediaTask.model_validate(response.json())
    except (ValidationError, ValueError) as exc:
        raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False) from exc


def _raise_for_error(response: httpx.Response) -> None:
    if response.is_success:
        return
    error_type: str | None = None
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        payload = cast(dict[str, object], body)
        error = payload.get("error")
        if isinstance(error, dict):
            error_payload = cast(dict[str, object], error)
            candidate = error_payload.get("type")
            error_type = candidate if isinstance(candidate, str) else None
    mapped = map_provider_error(response.status_code, error_type)
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None and retry_after.isdigit():
        mapped.retry_after_seconds = int(retry_after)
    raise mapped


def _request_id(response: httpx.Response) -> str | None:
    value = response.headers.get("X-Request-ID")
    if value is None or not value.strip() or len(value) > 255:
        return None
    return value


async def _persist_video(
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
    key: str,
    sha256: str,
    size_bytes: int,
    mime_type: str,
) -> GeneratedFileFact:
    if (
        stored.storage_key != key
        or stored.size_bytes != size_bytes
        or stored.mime_type != mime_type
        or stored.sha256 != sha256
    ):
        raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
    return GeneratedFileFact(
        storage_key=key,
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


def _delete_temporary_file(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)
