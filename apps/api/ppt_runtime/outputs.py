"""Validated PPT render results and immutable Artifact payloads."""

from __future__ import annotations

import json
from typing import Any

from apps.api.assets.ppt_runtime_contracts import PptxFileVersionFact, PublishedPptxObject
from apps.api.ppt_rendering.models import AssemblyManifest

from .contracts import PptRenderProduct, PreparedPptRuntime
from .materials import ASSEMBLE_EXECUTOR, EXPORT_EXECUTOR, error


def require_render_product(
    prepared: PreparedPptRuntime,
    product: PptRenderProduct,
    published: PublishedPptxObject | None,
) -> None:
    manifest = product.manifest
    if len(manifest.pages) != len(prepared.backgrounds):
        raise error("PPT_RUNTIME_RENDER_RESULT_INVALID", "the rendered page count differs")
    for page, background in zip(manifest.pages, prepared.backgrounds, strict=True):
        if (
            page.page_key != background.page_key
            or page.position != background.position
            or page.background_sha256 != background.sha256
            or page.background_media_type != background.mime_type
            or page.background_size_bytes != background.size_bytes
            or page.background_width != background.width
            or page.background_height != background.height
        ):
            raise error(
                "PPT_RUNTIME_RENDER_RESULT_INVALID",
                "a rendered page differs from its frozen background fact",
            )
    is_export = prepared.definition.executor_ref == EXPORT_EXECUTOR
    if is_export != (product.pptx is not None and published is not None):
        raise error(
            "PPT_RUNTIME_RENDER_RESULT_INVALID",
            "the deterministic executor returned the wrong result kind",
        )
    if product.pptx is not None and published is not None:
        if (
            product.pptx.assembly_manifest != manifest
            or published.mime_type != product.pptx.media_type
            or published.size_bytes != product.pptx.size_bytes
            or published.sha256 != product.pptx.sha256
        ):
            raise error(
                "PPT_RUNTIME_PUBLISHED_OBJECT_MISMATCH",
                "the published PPTX differs from the render result",
            )


def artifact_content(
    prepared: PreparedPptRuntime,
    manifest: AssemblyManifest,
    file_fact: PptxFileVersionFact | None,
) -> dict[str, Any]:
    if prepared.definition.executor_ref == ASSEMBLE_EXECUTOR:
        return _assembly_content(prepared, manifest)
    if (
        prepared.definition.executor_ref != EXPORT_EXECUTOR
        or file_fact is None
        or prepared.assembly_artifact_version_id is None
    ):
        raise error("PPT_RUNTIME_FILE_FACT_MISSING", "the exported PPTX file fact is missing")
    return {
        "implementation_version": manifest.implementation_version,
        "assembly_artifact_version_id": str(prepared.assembly_artifact_version_id),
        "source_page_spec_version_id": str(prepared.page_spec_version_id),
        "file_asset_version_id": str(file_fact.file_asset_version_id),
        "mime_type": file_fact.mime_type,
        "size_bytes": file_fact.size_bytes,
        "sha256": file_fact.sha256,
        "page_count": file_fact.page_count,
        "background_file_asset_version_ids": [
            str(item.file_asset_version_id) for item in prepared.backgrounds
        ],
    }


def output_bytes(product: PptRenderProduct) -> int:
    if product.pptx is not None:
        return product.pptx.size_bytes
    payload = json.dumps(
        product.manifest.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return len(payload)


def _assembly_content(
    prepared: PreparedPptRuntime,
    manifest: AssemblyManifest,
) -> dict[str, Any]:
    page_spec_set_key = prepared.page_spec_content.get("page_spec_set_key")
    if type(page_spec_set_key) is not str or not page_spec_set_key:
        raise error(
            "PPT_RUNTIME_PAGE_SPECS_INVALID",
            "the page specification set key is missing",
        )
    return {
        "implementation_version": manifest.implementation_version,
        "content_hash": manifest.content_hash,
        "source_page_spec_version_id": str(prepared.page_spec_version_id),
        "source_page_spec_set_key": page_spec_set_key,
        "page_count": len(manifest.pages),
        "pages": [
            {
                "page_key": page.page_key,
                "position": page.position,
                "background_file_asset_version_id": str(background.file_asset_version_id),
                "background_sha256": page.background_sha256,
                "background_media_type": page.background_media_type,
                "background_size_bytes": page.background_size_bytes,
                "background_width": page.background_width,
                "background_height": page.background_height,
                "elements": [element.model_dump(mode="json") for element in page.elements],
            }
            for page, background in zip(manifest.pages, prepared.backgrounds, strict=True)
        ],
    }
