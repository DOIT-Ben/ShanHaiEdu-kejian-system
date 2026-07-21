"""Internal render Port frozen by Issue #169."""

from typing import Protocol

from apps.api.ppt_rendering.models import AssemblyManifest, AssemblyRequest, PptxFileFact


class PptRenderingPort(Protocol):
    def assemble_pages(self, request: AssemblyRequest) -> AssemblyManifest: ...

    def export_pptx(self, request: AssemblyRequest) -> PptxFileFact: ...
