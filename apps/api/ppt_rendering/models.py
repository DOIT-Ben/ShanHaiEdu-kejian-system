"""Immutable value objects for deterministic PPT assembly and export."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

SLIDE_WIDTH_EMU = 12_192_000
SLIDE_HEIGHT_EMU = 6_858_000
PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
IMPLEMENTATION_VERSION = "ppt-render-core/1"

ElementKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
PageKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Color = Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{6}$")]
TextKind = Literal["title", "body", "number", "formula", "answer", "annotation"]
ShapeKind = Literal["rectangle", "ellipse", "line", "arrow"]


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CanvasSpec(_FrozenModel):
    width: int = Field(default=SLIDE_WIDTH_EMU, gt=0)
    height: int = Field(default=SLIDE_HEIGHT_EMU, gt=0)
    safe_margin: int = Field(default=457_200, ge=0)


class Box(_FrozenModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class FontStyle(_FrozenModel):
    family: str = Field(default="Microsoft YaHei", min_length=1, max_length=100)
    size_points: int = Field(default=18, ge=6, le=200)
    bold: bool = False
    italic: bool = False
    color: Color = "000000"
    align: Literal["left", "center", "right"] = "left"

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str) -> str:
        return value.upper()


class BackgroundImage(_FrozenModel):
    content: bytes = Field(min_length=1)
    media_type: Literal["image/png", "image/jpeg"]


class TextElement(_FrozenModel):
    element_type: Literal["text"] = "text"
    element_key: ElementKey
    kind: TextKind
    text: str = Field(min_length=1, max_length=20_000)
    box: Box
    font: FontStyle = FontStyle()


class ShapeElement(_FrozenModel):
    element_type: Literal["shape"] = "shape"
    element_key: ElementKey
    kind: ShapeKind
    box: Box
    fill_color: Color | None = None
    line_color: Color = "000000"
    line_width_points: int = Field(default=1, ge=1, le=20)

    @field_validator("fill_color", "line_color")
    @classmethod
    def normalize_optional_color(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


EditableElement = TextElement | ShapeElement


class PageSpec(_FrozenModel):
    page_key: PageKey
    position: int = Field(ge=1)
    backgrounds: tuple[BackgroundImage, ...]
    elements: tuple[EditableElement, ...]


class AssemblyRequest(_FrozenModel):
    canvas: CanvasSpec = CanvasSpec()
    pages: tuple[PageSpec, ...]


class ManifestElement(_FrozenModel):
    element_key: str
    element_type: Literal["text", "shape"]
    kind: str
    editability: Literal["native", "editable_text_fallback"]
    box: Box


class ManifestPage(_FrozenModel):
    page_key: str
    position: int
    background_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    background_media_type: Literal["image/png", "image/jpeg"]
    background_size_bytes: int = Field(gt=0)
    elements: tuple[ManifestElement, ...]


class AssemblyManifest(_FrozenModel):
    implementation_version: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    canvas: CanvasSpec
    pages: tuple[ManifestPage, ...]


class PptxFileFact(_FrozenModel):
    implementation_version: str
    media_type: Literal["application/vnd.openxmlformats-officedocument.presentationml.presentation"]
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content: bytes = Field(min_length=1)
    assembly_manifest: AssemblyManifest
