from __future__ import annotations

import base64
import struct
import zlib

from apps.api.ppt_rendering import (
    AssemblyRequest,
    BackgroundImage,
    Box,
    CanvasSpec,
    FontStyle,
    PageSpec,
    ShapeElement,
    TextElement,
)


def png_bytes(
    *,
    width: int = 160,
    height: int = 90,
    red: int = 245,
    green: int = 248,
    blue: int = 255,
) -> bytes:
    """Build a dependency-free RGB PNG fixture."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes((red, green, blue)) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def jpeg_bytes() -> bytes:
    """Return a dependency-free baseline 160x90 JPEG fixture."""

    return base64.b64decode(
        "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoH"
        "BwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQME"
        "BAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU"
        "FBQUFBQUFBQUFBQUFBT/wAARCABaAKADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEA"
        "AAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIh"
        "MUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6"
        "Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZ"
        "mqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx"
        "8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREA"
        "AgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAV"
        "YnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hp"
        "anN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPE"
        "xcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD9"
        "O6KKK7TiCiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAoo"
        "ooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAoo"
        "ooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAoo"
        "ooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAoo"
        "ooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAoo"
        "ooAKKKKACiiigAooooA//9k="
    )


def make_page(*, page_key: str = "page-1", position: int = 1) -> PageSpec:
    return PageSpec(
        page_key=page_key,
        position=position,
        backgrounds=(
            BackgroundImage(
                content=png_bytes(red=240 - position, green=248, blue=255),
                media_type="image/png",
            ),
        ),
        elements=(
            TextElement(
                element_key=f"{page_key}-title",
                kind="title",
                text="认识百分数",
                box=Box(x=914_400, y=457_200, width=10_668_000, height=914_400),
                font=FontStyle(size_points=28, bold=True, color="17365D"),
            ),
            TextElement(
                element_key=f"{page_key}-body",
                kind="body",
                text="把整体平均分成100份。",
                box=Box(x=914_400, y=1_828_800, width=5_486_400, height=914_400),
                font=FontStyle(size_points=20, color="203864"),
            ),
            TextElement(
                element_key=f"{page_key}-number",
                kind="number",
                text="25%",
                box=Box(x=914_400, y=3_200_400, width=2_743_200, height=914_400),
                font=FontStyle(size_points=32, bold=True, color="C65911"),
            ),
            TextElement(
                element_key=f"{page_key}-formula",
                kind="formula",
                text="25% = 25 / 100",
                box=Box(x=914_400, y=4_343_400, width=4_572_000, height=685_800),
                font=FontStyle(size_points=18, color="203864"),
            ),
            ShapeElement(
                element_key=f"{page_key}-shape",
                kind="ellipse",
                box=Box(x=7_315_200, y=2_057_400, width=2_286_000, height=2_286_000),
                fill_color="FFD966",
                line_color="C55A11",
                line_width_points=2,
            ),
        ),
    )


def make_request(*, pages: tuple[PageSpec, ...] | None = None) -> AssemblyRequest:
    return AssemblyRequest(
        canvas=CanvasSpec(),
        pages=pages or (make_page(),),
    )
