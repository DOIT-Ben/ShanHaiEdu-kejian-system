"""Argument parsing and command dispatch for administrative CLI commands."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from apps.api.cli import (
    run_model_smoke,
    run_provider_media_cleanup,
    run_publish_golden_content,
    run_video_smoke,
)
from apps.api.model_gateway.contracts import ModelCapability


def main() -> int:
    parser = argparse.ArgumentParser(description="ShanHaiEdu administrative commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    smoke = subparsers.add_parser("model-smoke", help="run an explicit text model smoke")
    smoke.add_argument(
        "--capability",
        choices=[ModelCapability.TEXT_SMOKE.value],
        required=True,
    )
    smoke.add_argument("--real", action="store_true")
    video_smoke = subparsers.add_parser(
        "video-smoke",
        help="run an explicit billable video Provider smoke",
    )
    video_smoke.add_argument("--prompt", required=True)
    video_smoke.add_argument("--duration-seconds", type=int, default=6)
    video_smoke.add_argument("--output-dir", type=Path)
    video_smoke.add_argument("--organization-id", type=UUID)
    video_smoke.add_argument("--file-version-id", type=UUID)
    video_smoke.add_argument("--real", action="store_true")
    subparsers.add_parser(
        "publish-golden-content",
        help="publish the validated built-in content package and activate it for new projects",
    )
    subparsers.add_parser(
        "provider-media-cleanup",
        help="remove expired opaque provider-media relay files",
    )
    args = parser.parse_args()
    if args.command == "model-smoke":
        return asyncio.run(
            run_model_smoke(
                capability=ModelCapability(args.capability),
                real=bool(args.real),
            )
        )
    if args.command == "video-smoke":
        if not args.real:
            parser.error("video-smoke requires --real")
        return asyncio.run(
            run_video_smoke(
                prompt=args.prompt,
                duration_seconds=args.duration_seconds,
                output_dir=args.output_dir,
                organization_id=args.organization_id,
                file_version_id=args.file_version_id,
            )
        )
    if args.command == "publish-golden-content":
        return run_publish_golden_content()
    if args.command == "provider-media-cleanup":
        return run_provider_media_cleanup()
    return 2
