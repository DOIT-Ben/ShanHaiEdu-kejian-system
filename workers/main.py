"""Worker bootstrap. Business task processing is introduced by Issue #8."""

from __future__ import annotations

import argparse
import asyncio
import logging

from apps.api.health import build_readiness_service
from apps.api.logging import configure_logging
from apps.api.settings import get_settings

logger = logging.getLogger(__name__)


async def run_worker(*, check_only: bool) -> int:
    settings = get_settings()
    configure_logging(
        service="shanhaiedu-worker",
        environment=settings.environment,
        level=settings.log_level,
    )
    report = await build_readiness_service(settings).check()
    if not report.ready:
        logger.error("worker_dependencies_not_ready", extra={"ready": False})
        return 1

    logger.info("worker_booted", extra={"ready": True, "task_processing_enabled": False})
    if check_only:
        return 0

    await asyncio.Event().wait()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the ShanHaiEdu worker bootstrap")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify dependencies and exit without starting the long-running process",
    )
    args = parser.parse_args()
    return asyncio.run(run_worker(check_only=bool(args.check)))


if __name__ == "__main__":
    raise SystemExit(main())
