"""Provider-neutral deterministic PPT rendering core."""

from apps.api.ppt_rendering.errors import PptRenderingError
from apps.api.ppt_rendering.models import (
    IMPLEMENTATION_VERSION,
    PPTX_MEDIA_TYPE,
    SLIDE_HEIGHT_EMU,
    SLIDE_WIDTH_EMU,
    AssemblyManifest,
    AssemblyRequest,
    BackgroundImage,
    Box,
    CanvasSpec,
    FontStyle,
    ManifestElement,
    ManifestPage,
    PageSpec,
    PptxFileFact,
    ShapeElement,
    TextElement,
)
from apps.api.ppt_rendering.ports import PptRenderingPort
from apps.api.ppt_rendering.service import assemble_pages, export_pptx

__all__ = [
    "IMPLEMENTATION_VERSION",
    "PPTX_MEDIA_TYPE",
    "SLIDE_HEIGHT_EMU",
    "SLIDE_WIDTH_EMU",
    "AssemblyManifest",
    "AssemblyRequest",
    "BackgroundImage",
    "Box",
    "CanvasSpec",
    "FontStyle",
    "ManifestElement",
    "ManifestPage",
    "PageSpec",
    "PptRenderingError",
    "PptRenderingPort",
    "PptxFileFact",
    "ShapeElement",
    "TextElement",
    "assemble_pages",
    "export_pptx",
]
