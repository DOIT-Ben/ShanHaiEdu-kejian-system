"""Material PDF parsing worker with lease recovery and durable idempotency."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.assets.material_parser import (
    MaterialParser,
    MaterialParserError,
    MaterialParseSource,
    ParseLimits,
)
from apps.api.assets.models import FileAsset, FileAssetVersion, MaterialParseVersion
from apps.api.assets.pypdf_parser import PypdfMaterialParser
from apps.api.assets.service import MaterialParseService
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import ActorContext, system_actor
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.service import GenerationJobService
from apps.api.settings import Settings, get_settings
from apps.api.uploads.models import SourceMaterial
from apps.api.uploads.storage import ObjectStorage, ObjectStorageError, build_object_storage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParseInput:
    material_id: UUID
    version: FileAssetVersion


class MaterialParseJobRunner:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        storage: ObjectStorage,
        parser: MaterialParser,
        limits: ParseLimits,
        settings: Settings,
        temp_root: Path | None = None,
    ) -> None:
        self._factory = session_factory
        self._storage = storage
        self._parser = parser
        self._limits = limits
        self._settings = settings
        self._temp_root = temp_root

    def run(self, job_id: UUID, *, worker_id: str) -> str:
        actor = self._actor_for_job(job_id)
        if actor is None:
            return "ignored"
        prepared = self._claim_and_prepare(job_id, worker_id=worker_id, actor=actor)
        if prepared is None:
            return "ignored"
        parse_id, parse_input, terminal_status = prepared
        if terminal_status is not None:
            return terminal_status
        try:
            self._validate_parse_input(parse_input.version)
            progress_state = self._update_progress(
                job_id,
                worker_id=worker_id,
                actor=actor,
                progress_percent=20,
                message="Downloading confirmed material PDF",
            )
            if progress_state != "active":
                return self._stop_inactive_execution(
                    progress_state,
                    job_id=job_id,
                    parse_id=parse_id,
                    worker_id=worker_id,
                    actor=actor,
                )
            with tempfile.TemporaryDirectory(
                prefix="shanhai-material-parse-",
                dir=self._temp_root,
            ) as temp_directory:
                local_path = Path(temp_directory) / "source.pdf"
                self._storage.download_to_path(
                    bucket=parse_input.version.storage_bucket,
                    key=parse_input.version.storage_key,
                    destination=local_path,
                    max_bytes=self._limits.max_file_bytes,
                )
                progress_state = self._update_progress(
                    job_id,
                    worker_id=worker_id,
                    actor=actor,
                    progress_percent=45,
                    message="Parsing material PDF in an isolated process",
                )
                if progress_state != "active":
                    return self._stop_inactive_execution(
                        progress_state,
                        job_id=job_id,
                        parse_id=parse_id,
                        worker_id=worker_id,
                        actor=actor,
                    )
                result = self._parser.parse(
                    local_path,
                    MaterialParseSource(
                        file_asset_version_id=parse_input.version.id,
                        sha256=parse_input.version.sha256,
                        mime_type=parse_input.version.mime_type,
                        byte_size=parse_input.version.byte_size,
                    ),
                    self._limits,
                )
        except MaterialParserError as exc:
            return self._record_failure(
                job_id,
                parse_id=parse_id,
                worker_id=worker_id,
                actor=actor,
                error_code=exc.code,
            )
        except ObjectStorageError:
            return self._record_failure(
                job_id,
                parse_id=parse_id,
                worker_id=worker_id,
                actor=actor,
                error_code="PDF_SOURCE_UNAVAILABLE",
            )
        except Exception:
            logger.exception("material_parse_worker_failed", extra={"job_id": str(job_id)})
            self._record_failure(
                job_id,
                parse_id=parse_id,
                worker_id=worker_id,
                actor=actor,
                error_code="PDF_PARSE_INTERNAL_ERROR",
            )
            raise
        return self._record_success(
            job_id,
            parse_id=parse_id,
            worker_id=worker_id,
            actor=actor,
            result=result,
        )

    def _validate_parse_input(self, version: FileAssetVersion) -> None:
        media_type = version.mime_type.lower().split(";", maxsplit=1)[0].strip()
        if media_type != "application/pdf":
            raise MaterialParserError("PDF_MIME_UNSUPPORTED")
        if version.byte_size > self._limits.max_file_bytes:
            raise MaterialParserError("PDF_SIZE_LIMIT_EXCEEDED")

    def _actor_for_job(self, job_id: UUID) -> ActorContext | None:
        with self._factory() as session:
            organization_id = session.scalar(
                select(GenerationJob.organization_id).where(GenerationJob.id == job_id)
            )
        return system_actor(organization_id) if organization_id is not None else None

    def _claim_and_prepare(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        actor: ActorContext,
    ) -> tuple[UUID, ParseInput, str | None] | None:
        with self._factory() as session, session.begin():
            jobs = self._jobs(session, actor)
            claimed = jobs.claim(
                job_id,
                worker_id=worker_id,
                lease_seconds=max(
                    self._settings.worker_lease_seconds,
                    ceil(self._limits.timeout_seconds) + 30,
                ),
            )
            if claimed is None:
                return None
            if claimed.job_type != "material.parse" or claimed.source_material_id is None:
                jobs.complete(job_id, worker_id=worker_id, error_code="JOB_TYPE_UNSUPPORTED")
                return None
            parse_input = self._load_parse_input(session, claimed)
            parses = MaterialParseService(session, actor)
            parse = parses.create(
                parse_input.material_id,
                parse_input.version.id,
                parser_name=self._parser.name,
                parser_version=self._parser.version,
                generation_job_id=job_id,
            )
            if parse.status == "pending":
                parse = parses.start(parse.id)
            elif parse.status == "succeeded":
                jobs.complete(job_id, worker_id=worker_id)
                return parse.id, parse_input, "succeeded"
            elif parse.status == "failed":
                jobs.complete(job_id, worker_id=worker_id, error_code=parse.error_code)
                return parse.id, parse_input, "failed"
            return parse.id, parse_input, None

    def _load_parse_input(self, session: Session, job: GenerationJob) -> ParseInput:
        row = session.execute(
            select(SourceMaterial, FileAssetVersion)
            .join(FileAsset, FileAsset.id == SourceMaterial.file_asset_id)
            .join(FileAssetVersion, FileAssetVersion.id == FileAsset.current_version_id)
            .where(
                SourceMaterial.id == job.source_material_id,
                SourceMaterial.organization_id == job.organization_id,
                SourceMaterial.upload_status == "confirmed",
                SourceMaterial.deleted_at.is_(None),
                FileAsset.organization_id == job.organization_id,
                FileAsset.deleted_at.is_(None),
                FileAssetVersion.organization_id == job.organization_id,
            )
            .with_for_update(of=(SourceMaterial, FileAsset))
        ).one_or_none()
        if row is None:
            raise MaterialParserError("PDF_SOURCE_UNAVAILABLE")
        return ParseInput(material_id=row[0].id, version=row[1])

    def _update_progress(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        actor: ActorContext,
        progress_percent: int,
        message: str,
    ) -> str:
        with self._factory() as session, session.begin():
            updated = self._jobs(session, actor).update_progress(
                job_id,
                worker_id=worker_id,
                progress_percent=progress_percent,
                message=message,
            )
            if updated is not None:
                return "cancelled" if updated.status == "cancel_requested" else "active"
            persisted = session.get(GenerationJob, job_id)
            if persisted is not None and (
                persisted.status == "cancel_requested" or persisted.cancel_requested_at is not None
            ):
                return "cancelled"
            return "lost"

    def _stop_inactive_execution(
        self,
        state: str,
        *,
        job_id: UUID,
        parse_id: UUID,
        worker_id: str,
        actor: ActorContext,
    ) -> str:
        if state == "cancelled":
            return self._record_failure(
                job_id,
                parse_id=parse_id,
                worker_id=worker_id,
                actor=actor,
                error_code="PDF_PARSE_CANCELLED",
            )
        return "ignored"

    def _record_success(
        self,
        job_id: UUID,
        *,
        parse_id: UUID,
        worker_id: str,
        actor: ActorContext,
        result: object,
    ) -> str:
        from apps.api.assets.material_parser import MaterialParseResult

        if not isinstance(result, MaterialParseResult):
            raise TypeError("material parser returned an invalid result")
        with self._factory() as session, session.begin():
            job = session.get(GenerationJob, job_id, with_for_update=True)
            parse = session.get(MaterialParseVersion, parse_id, with_for_update=True)
            if job is None or parse is None:
                raise RuntimeError("material parse execution state disappeared")
            if job.status == "cancel_requested" or job.cancel_requested_at is not None:
                if parse.status == "running":
                    MaterialParseService(session, actor).fail(
                        parse_id,
                        error_code="PDF_PARSE_CANCELLED",
                        validation_report=_failure_report("PDF_PARSE_CANCELLED"),
                    )
                self._jobs(session, actor).complete(job_id, worker_id=worker_id)
                return "cancelled"
            if job.status != "running" or job.lease_owner != worker_id:
                return "ignored"
            if parse.status == "running":
                MaterialParseService(session, actor).complete(
                    parse_id,
                    content=result.evidence,
                    page_count=result.page_count,
                    text_checksum=result.text_checksum,
                    validation_report=result.validation_report,
                )
            self._jobs(session, actor).complete(job_id, worker_id=worker_id)
            return "succeeded"

    def _record_failure(
        self,
        job_id: UUID,
        *,
        parse_id: UUID,
        worker_id: str,
        actor: ActorContext,
        error_code: str,
    ) -> str:
        with self._factory() as session, session.begin():
            job = session.get(GenerationJob, job_id, with_for_update=True)
            parse = session.get(MaterialParseVersion, parse_id, with_for_update=True)
            if job is None or parse is None:
                raise RuntimeError("material parse execution state disappeared")
            cancelled = job.status == "cancel_requested" or job.cancel_requested_at is not None
            if not cancelled and (job.status != "running" or job.lease_owner != worker_id):
                return "ignored"
            persisted_error = "PDF_PARSE_CANCELLED" if cancelled else error_code
            if parse.status == "running":
                MaterialParseService(session, actor).fail(
                    parse_id,
                    error_code=persisted_error,
                    validation_report=_failure_report(persisted_error),
                )
            self._jobs(session, actor).complete(
                job_id,
                worker_id=worker_id,
                error_code=None if cancelled else error_code,
            )
            return "cancelled" if cancelled else "failed"

    def _jobs(self, session: Session, actor: ActorContext) -> GenerationJobService:
        return GenerationJobService(
            session,
            actor=actor,
            idempotency_ttl_seconds=self._settings.idempotency_ttl_seconds,
        )


def run_material_parse_job(job_id: UUID, *, worker_id: str) -> str:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("worker database persistence is not configured")
    storage = build_object_storage(settings)
    if storage is None:
        raise RuntimeError("worker object storage is not configured")
    engine = build_engine(settings.database_url.get_secret_value())
    try:
        return MaterialParseJobRunner(
            build_session_factory(engine),
            storage=storage,
            parser=PypdfMaterialParser(),
            limits=ParseLimits(
                max_file_bytes=settings.max_upload_size_bytes,
                max_pages=settings.material_parse_max_pages,
                max_text_chars=settings.material_parse_max_text_chars,
                max_text_blocks=settings.material_parse_max_text_blocks,
                max_image_references=settings.material_parse_max_image_references,
                timeout_seconds=settings.material_parse_timeout_seconds,
            ),
            settings=settings,
        ).run(job_id, worker_id=worker_id)
    finally:
        engine.dispose()


def _failure_report(error_code: str) -> dict[str, object]:
    return {
        "valid": False,
        "schema_version": "material-evidence-package.v1",
        "error_code": error_code,
        "errors": [],
    }
