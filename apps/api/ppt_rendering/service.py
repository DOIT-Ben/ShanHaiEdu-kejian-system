"""Pure application functions for assembly and deterministic PPTX export."""

import hashlib

from apps.api.ppt_rendering.models import (
    IMPLEMENTATION_VERSION,
    PPTX_MEDIA_TYPE,
    AssemblyManifest,
    AssemblyRequest,
    PptxFileFact,
)
from apps.api.ppt_rendering.ooxml import render_pptx
from apps.api.ppt_rendering.validation import build_manifest


def assemble_pages(request: AssemblyRequest) -> AssemblyManifest:
    return build_manifest(request)


def export_pptx(request: AssemblyRequest) -> PptxFileFact:
    manifest = assemble_pages(request)
    content = render_pptx(request)
    return PptxFileFact(
        implementation_version=IMPLEMENTATION_VERSION,
        media_type=PPTX_MEDIA_TYPE,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
        assembly_manifest=manifest,
    )
