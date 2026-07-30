"""Run the real queue/worker path with deterministic R1 text outputs for browser CI."""

from __future__ import annotations

import asyncio
import hashlib
import json
import signal
import socket
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from threading import Event
from uuid import UUID

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.worker import Worker

from apps.api.database import build_engine, build_session_factory
from apps.api.jobs.models import GenerationJob
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.contracts import (
    GeneratedFileFact,
    ModelCapability,
    ModelUsage,
    TextModelRequest,
    TextProviderResult,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
    VideoProviderResult,
)
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.reliability.models import OutboxEvent
from apps.api.reliability.outbox import OutboxDispatcher
from apps.api.settings import get_settings
from apps.api.uploads.storage import ObjectStorage, build_object_storage
from scripts.golden_courseware_branch_inputs import (
    build_golden_branch_source_outputs,
    build_intro_generation_stage_outputs,
)
from workers.video_generation import execute_video_generation_job

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


class R1RescueNodeOutputProvider:
    provider_name = "r1-rescue-deterministic"
    model_name = "r1-rescue-node-output-v1"

    def __init__(self, outputs: dict[str, dict[str, object]]) -> None:
        self._outputs = outputs
        self._intro_stages = build_intro_generation_stage_outputs(outputs["intro.generate_options"])

    async def complete(self, request: TextModelRequest) -> TextProviderResult:
        if request.capability == ModelCapability.TEXT_STRUCTURED_CREATIVE_EDUCATION:
            output = (
                self._intro_stages[1]
                if "Exact candidate pool JSON:" in request.prompt
                else self._intro_stages[0]
            )
        elif '"lesson_plan_key"' in request.prompt:
            output = self._outputs["lesson_plan.generate"]
        elif '"division_key"' in request.prompt:
            output = self._outputs["lesson.division.generate"]
        else:
            raise RuntimeError("the R1 E2E provider received an unsupported output contract")
        return TextProviderResult(
            text=json.dumps(
                output,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ),
            provider_request_id=f"fake:{request.request_id}",
            actual_model=self.model_name,
            finish_reason="stop",
            usage=ModelUsage(
                prompt_tokens=8,
                completion_tokens=4,
                total_tokens=12,
                cost=Decimal("0"),
            ),
        )


class R1RescueVideoProvider:
    provider_name = "r1-rescue-deterministic"
    model_name = "r1-rescue-video-6s-v1"

    def __init__(self, storage: ObjectStorage, *, bucket: str, payload: bytes) -> None:
        self._storage = storage
        self._bucket = bucket
        self._payload = payload
        self._tasks: set[str] = set()

    async def submit(
        self,
        request: VideoModelRequest,
        *,
        organization_id: UUID | None = None,
    ) -> VideoProviderResult:
        if organization_id is None or request.duration_seconds != 6 or len(request.references) != 1:
            raise RuntimeError("the R1 E2E video provider received an invalid request")
        task_id = f"r1-video:{request.request_id}"
        self._tasks.add(task_id)
        return self._result(request.request_id, task_id, VideoOperationStatus.SUBMITTED)

    async def poll(self, request: VideoPollRequest) -> VideoProviderResult:
        if request.provider_task_id not in self._tasks:
            raise RuntimeError("the R1 E2E video provider received an unknown task")
        digest = hashlib.sha256(request.provider_task_id.encode("utf-8")).hexdigest()
        key = f"e2e/video-golden-slice/{digest}.mp4"
        metadata = self._storage.put_bytes(
            bucket=self._bucket,
            key=key,
            payload=self._payload,
            media_type="video/mp4",
        )
        return VideoProviderResult(
            status=VideoOperationStatus.SUCCEEDED,
            provider_request_id=f"fake:{request.request_id}",
            provider_task_id=request.provider_task_id,
            actual_model=self.model_name,
            files=[
                GeneratedFileFact(
                    storage_key=key,
                    sha256=metadata.sha256 or "",
                    size_bytes=metadata.size_bytes,
                    mime_type="video/mp4",
                    duration_seconds=6,
                )
            ],
            usage=ModelUsage(output_units={"video_seconds": 6}),
        )

    async def cancel(self, request: VideoPollRequest) -> VideoProviderResult:
        return self._result(
            request.request_id,
            request.provider_task_id,
            VideoOperationStatus.CANCELLED,
        )

    def _result(
        self,
        request_id: str,
        task_id: str,
        status: VideoOperationStatus,
    ) -> VideoProviderResult:
        return VideoProviderResult(
            status=status,
            provider_request_id=f"fake:{request_id}",
            provider_task_id=task_id,
            actual_model=self.model_name,
            usage=ModelUsage(),
        )


def _six_second_video() -> bytes:
    with tempfile.TemporaryDirectory(prefix="shanhai-r1-video-e2e-") as directory:
        output = Path(directory) / "six-second.mp4"
        completed = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=320x180:d=6:r=12",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-y",
                str(output),
            ],
            check=False,
            capture_output=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "the R1 E2E video fixture could not be generated: "
                + completed.stderr.decode("utf-8", errors="replace")
            )
        return output.read_bytes()


def main() -> int:
    settings = get_settings()
    if (
        settings.environment != "test"
        or settings.database_url is None
        or settings.redis_url is None
    ):
        raise RuntimeError("the rescue E2E worker requires test PostgreSQL and Redis")

    broker = RedisBroker(url=settings.redis_url.get_secret_value())
    dramatiq.set_broker(broker)
    from workers import artifact_quality as quality_tasks
    from workers import tasks as generation_tasks
    from workers.node_execution import execute_node_execution_job

    engine = build_engine(settings.database_url.get_secret_value())
    factory = build_session_factory(engine)
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    outputs = build_golden_branch_source_outputs(case)
    outputs["lesson.division.generate"]["lesson_units"][0]["evidence_refs"] = ["p2-text-1"]
    provider = R1RescueNodeOutputProvider(outputs)
    storage = build_object_storage(settings)
    if storage is None:
        raise RuntimeError("the rescue E2E worker requires object storage")
    video_provider = R1RescueVideoProvider(
        storage,
        bucket=settings.object_storage_bucket,
        payload=_six_second_video(),
    )
    gateway = ModelGateway(
        {
            ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider,
            ModelCapability.TEXT_STRUCTURED_CREATIVE_EDUCATION: provider,
        },
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: video_provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )

    original_run_generation_job = generation_tasks.run_generation_job

    def run_fixture_generation(job_id: UUID, *, worker_id: str | None = None) -> str:
        with factory() as session:
            job = session.get(GenerationJob, job_id)
            job_type = job.job_type if job is not None else None
        if job_type == "material.parse":
            return original_run_generation_job(job_id, worker_id=worker_id)
        if job_type == "video.golden_slice":
            return asyncio.run(
                execute_video_generation_job(
                    job_id,
                    worker_id=worker_id or "r1-rescue-e2e-worker",
                    gateway=gateway,
                    storage=storage,
                    settings=settings,
                )
            )
        return asyncio.run(
            execute_node_execution_job(
                job_id,
                worker_id=worker_id or "r1-rescue-e2e-worker",
                model=gateway,
                settings=settings,
            )
        )

    generation_tasks.run_generation_job = run_fixture_generation
    dispatcher = OutboxDispatcher(
        factory,
        worker_id=f"{socket.gethostname()}:r1-rescue-e2e",
        lease_seconds=settings.worker_lease_seconds,
        retry_seconds=settings.outbox_retry_seconds,
    )

    def publish(event: OutboxEvent) -> None:
        if event.topic == "generation.job.queued":
            generation_tasks.process_generation_job.send(str(event.aggregate_id))
        elif event.topic == "artifact.quality_validation.queued":
            quality_tasks.process_artifact_quality_node.send(str(event.aggregate_id))

    stopping = Event()

    def stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    worker = Worker(broker, worker_threads=2)
    worker.start()
    print("r1 rescue e2e worker ready", flush=True)
    try:
        while not stopping.is_set():
            dispatcher.dispatch_batch(publish)
            stopping.wait(settings.outbox_poll_seconds)
    finally:
        worker.stop()
        broker.close()
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
