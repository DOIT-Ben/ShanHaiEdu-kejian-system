"""Dramatiq worker and transactional outbox dispatcher."""

from __future__ import annotations

import argparse
import asyncio
import logging
import socket
import time

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.worker import Worker

from apps.api.database import build_engine, build_session_factory
from apps.api.health import build_readiness_service
from apps.api.logging import configure_logging
from apps.api.reliability.models import OutboxEvent
from apps.api.reliability.outbox import OutboxDispatcher
from apps.api.settings import get_settings
from workers.recovery import WorkerRecoveryCoordinator

logger = logging.getLogger(__name__)


def _run_startup_recovery(coordinator: WorkerRecoveryCoordinator) -> None:
    result = coordinator.reconcile()
    logger.info(
        "generation_attempt_startup_recovery_completed",
        extra={
            "cancellation_requests": result.cancellation_requests,
            "recovered_attempts": result.recovered_attempts,
            "expired_recovery_facts": result.expired_recovery_facts,
        },
    )


async def check_dependencies() -> bool:
    settings = get_settings()
    report = await build_readiness_service(settings).check()
    if not report.ready:
        logger.error("worker_dependencies_not_ready", extra={"ready": False})
        return False
    return True


def run_worker(*, check_only: bool) -> int:
    settings = get_settings()
    configure_logging(
        service="shanhaiedu-worker",
        environment=settings.environment,
        level=settings.log_level,
    )
    if not asyncio.run(check_dependencies()):
        return 1
    if settings.database_url is None or settings.redis_url is None:
        logger.error("worker_runtime_configuration_missing")
        return 1

    broker = RedisBroker(url=settings.redis_url.get_secret_value())
    dramatiq.set_broker(broker)
    from workers.tasks import process_generation_job

    if check_only:
        logger.info(
            "worker_check_passed",
            extra={"registered_actor": process_generation_job.actor_name},
        )
        return 0

    engine = build_engine(settings.database_url.get_secret_value())
    factory = build_session_factory(engine)
    worker_id = f"{socket.gethostname()}:{id(broker)}"
    dispatcher = OutboxDispatcher(
        factory,
        worker_id=worker_id,
        lease_seconds=settings.worker_lease_seconds,
        retry_seconds=settings.outbox_retry_seconds,
    )
    recovery = WorkerRecoveryCoordinator(factory)

    def publish(event: OutboxEvent) -> None:
        if event.topic == "generation.job.queued":
            process_generation_job.send(str(event.aggregate_id))

    worker = Worker(broker, worker_threads=2)
    _run_startup_recovery(recovery)
    worker.start()
    logger.info("worker_booted", extra={"ready": True, "task_processing_enabled": True})
    try:
        while True:
            recovery.reconcile()
            dispatcher.dispatch_batch(publish)
            time.sleep(settings.outbox_poll_seconds)
    except KeyboardInterrupt:
        logger.info("worker_shutdown_requested")
    finally:
        worker.stop()
        engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the ShanHaiEdu worker bootstrap")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify dependencies and exit without starting the long-running process",
    )
    args = parser.parse_args()
    return run_worker(check_only=bool(args.check))


if __name__ == "__main__":
    raise SystemExit(main())
