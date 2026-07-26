"""Run the real queue/worker path with deterministic R1 text outputs for browser CI."""

from __future__ import annotations

import asyncio
import json
import signal
import socket
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
    ModelCapability,
    ModelUsage,
    TextModelRequest,
    TextProviderResult,
)
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.reliability.models import OutboxEvent
from apps.api.reliability.outbox import OutboxDispatcher
from apps.api.settings import get_settings
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


class R1RescueNodeOutputProvider:
    provider_name = "r1-rescue-deterministic"
    model_name = "r1-rescue-node-output-v1"

    def __init__(self, outputs: dict[str, dict[str, object]]) -> None:
        self._outputs = outputs

    async def complete(self, request: TextModelRequest) -> TextProviderResult:
        if request.capability == ModelCapability.TEXT_STRUCTURED_CREATIVE_EDUCATION:
            node_key = "intro.generate_options"
        elif '"lesson_plan_key"' in request.prompt:
            node_key = "lesson_plan.generate"
        elif '"division_key"' in request.prompt:
            node_key = "lesson.division.generate"
        else:
            raise RuntimeError("the R1 E2E provider received an unsupported output contract")
        return TextProviderResult(
            text=json.dumps(
                self._outputs[node_key],
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
    gateway = ModelGateway(
        {
            ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider,
            ModelCapability.TEXT_STRUCTURED_CREATIVE_EDUCATION: provider,
        },
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )

    original_run_generation_job = generation_tasks.run_generation_job

    def run_fixture_generation(job_id: UUID, *, worker_id: str | None = None) -> str:
        with factory() as session:
            job = session.get(GenerationJob, job_id)
            job_type = job.job_type if job is not None else None
        if job_type == "material.parse":
            return original_run_generation_job(job_id, worker_id=worker_id)
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
