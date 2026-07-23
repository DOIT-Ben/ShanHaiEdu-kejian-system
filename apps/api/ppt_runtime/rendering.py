"""Frozen-input rendering for deterministic PPT runtime executors."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from uuid import UUID

from apps.api.assets.ppt_runtime_contracts import PptBackgroundFact
from apps.api.ppt_rendering import (
    MAX_BACKGROUND_BYTES,
    AssemblyManifest,
    AssemblyRequest,
    CanvasSpec,
    ManifestPage,
    PptxFileFact,
)
from apps.api.ppt_rendering.ports import PptRenderingPort
from apps.api.ppt_rendering.service import assemble_pages, export_pptx
from apps.api.uploads.storage import ObjectMetadata, ObjectStorage

from .contracts import PptRenderProduct, PptRuntimeError, PreparedPptRuntime
from .layout import build_assembly_request
from .outputs import merge_page_manifests


class _BuiltInPptRenderer:
    def assemble_pages(self, request: AssemblyRequest) -> AssemblyManifest:
        return assemble_pages(request)

    def export_pptx(self, request: AssemblyRequest) -> PptxFileFact:
        return export_pptx(request)


class PptRuntimeRenderer:
    def __init__(
        self,
        storage: ObjectStorage,
        renderer: PptRenderingPort | None = None,
    ) -> None:
        self._storage = storage
        self._renderer = renderer or cast(PptRenderingPort, _BuiltInPptRenderer())

    def render(
        self,
        prepared: PreparedPptRuntime,
        completed_pages: list[ManifestPage],
    ) -> PptRenderProduct:
        with TemporaryDirectory(prefix="shanhai-ppt-runtime-") as directory:
            path = Path(directory)
            if prepared.definition.executor_ref == "executor.ppt.pages_assemble":
                return PptRenderProduct(
                    manifest=self._assemble_pages(prepared, path, completed_pages),
                    pptx=None,
                )
            if prepared.definition.executor_ref != "executor.ppt.pptx_export":
                raise PptRuntimeError(
                    "PPT_RUNTIME_EXECUTOR_UNSUPPORTED",
                    "the published deterministic PPT executor is unsupported",
                )
            payloads = self._download_backgrounds(prepared, path)
            request = build_assembly_request(
                prepared.page_spec_content,
                prepared.backgrounds,
                payloads,
            )
            result = self._renderer.export_pptx(request)
            _verify_assembly_input(prepared, result.assembly_manifest)
            return PptRenderProduct(manifest=result.assembly_manifest, pptx=result)

    def _assemble_pages(
        self,
        prepared: PreparedPptRuntime,
        directory: Path,
        completed_pages: list[ManifestPage],
    ) -> AssemblyManifest:
        source_pages = _page_spec_items(prepared.page_spec_content)
        if len(source_pages) != len(prepared.backgrounds):
            raise PptRuntimeError(
                "PPT_RUNTIME_PAGE_LAYOUT_INVALID",
                "the page and exact background counts differ",
            )
        for index in range(len(completed_pages), len(source_pages)):
            background = prepared.backgrounds[index]
            payload = self._download_background(background, directory, index)
            page_content = dict(prepared.page_spec_content)
            page_content["page_specs"] = [source_pages[index]]
            request = build_assembly_request(
                page_content,
                (background,),
                {background.file_asset_version_id: payload},
            )
            normalized = AssemblyRequest(
                canvas=request.canvas,
                pages=(request.pages[0].model_copy(update={"position": 1}),),
            )
            rendered = self._renderer.assemble_pages(normalized)
            if len(rendered.pages) != 1:
                raise PptRuntimeError(
                    "PPT_RUNTIME_RENDER_RESULT_INVALID",
                    "the page renderer returned an invalid page count",
                )
            completed_pages.append(
                rendered.pages[0].model_copy(update={"position": background.position})
            )
        return merge_page_manifests(CanvasSpec(), tuple(completed_pages))

    def _download_backgrounds(
        self,
        prepared: PreparedPptRuntime,
        directory: Path,
    ) -> dict[UUID, bytes]:
        return {
            fact.file_asset_version_id: self._download_background(fact, directory, index)
            for index, fact in enumerate(prepared.backgrounds)
        }

    def _download_background(
        self,
        fact: PptBackgroundFact,
        directory: Path,
        index: int,
    ) -> bytes:
        destination = directory / f"background-{index + 1:02d}.png"
        metadata = self._storage.download_to_path(
            bucket=fact.storage_bucket,
            key=fact.storage_key,
            destination=destination,
            max_bytes=MAX_BACKGROUND_BYTES,
        )
        if not _matches_background(metadata, fact):
            raise PptRuntimeError(
                "PPT_RUNTIME_BACKGROUND_OBJECT_MISMATCH",
                "an exact background object differs from its immutable file fact",
            )
        return destination.read_bytes()


def _verify_assembly_input(
    prepared: PreparedPptRuntime,
    manifest: AssemblyManifest,
) -> None:
    content = prepared.assembly_content
    if prepared.assembly_artifact_version_id is None or content is None:
        raise PptRuntimeError(
            "PPT_RUNTIME_ASSEMBLY_INPUT_MISSING",
            "PPTX export requires one exact approved assembly artifact",
        )
    expected_backgrounds = [str(item.file_asset_version_id) for item in prepared.backgrounds]
    raw_pages = content.get("pages")
    if not isinstance(raw_pages, Sequence) or isinstance(
        raw_pages,
        (str, bytes, bytearray),
    ):
        raise PptRuntimeError(
            "PPT_RUNTIME_ASSEMBLY_INPUT_INVALID",
            "the exact assembly artifact has no page facts",
        )
    actual_backgrounds: list[object] = []
    for page in cast(Sequence[object], raw_pages):
        if not isinstance(page, Mapping):
            raise PptRuntimeError(
                "PPT_RUNTIME_ASSEMBLY_INPUT_INVALID",
                "the exact assembly page facts are invalid",
            )
        actual_backgrounds.append(
            cast(Mapping[str, object], page).get("background_file_asset_version_id")
        )
    if (
        content.get("content_hash") != manifest.content_hash
        or content.get("source_page_spec_version_id") != str(prepared.page_spec_version_id)
        or content.get("page_count") != len(manifest.pages)
        or actual_backgrounds != expected_backgrounds
    ):
        raise PptRuntimeError(
            "PPT_RUNTIME_ASSEMBLY_INPUT_STALE",
            "the exact assembly artifact differs from the current render inputs",
        )


def _page_spec_items(content: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    raw = content.get("page_specs")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)) or not raw:
        raise PptRuntimeError(
            "PPT_RUNTIME_PAGE_LAYOUT_INVALID",
            "the exact page specification set is missing",
        )
    values = tuple(cast(Sequence[object], raw))
    if any(not isinstance(value, Mapping) for value in values):
        raise PptRuntimeError(
            "PPT_RUNTIME_PAGE_LAYOUT_INVALID",
            "the exact page specification set is invalid",
        )
    return cast(tuple[Mapping[str, object], ...], values)


def _matches_background(metadata: ObjectMetadata, fact: PptBackgroundFact) -> bool:
    return (
        metadata.bucket == fact.storage_bucket
        and metadata.key == fact.storage_key
        and metadata.media_type == fact.mime_type
        and metadata.size_bytes == fact.size_bytes
        and metadata.sha256 == fact.sha256
    )
