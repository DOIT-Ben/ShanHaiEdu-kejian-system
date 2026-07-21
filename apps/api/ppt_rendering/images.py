"""Dependency-free structural validation for supported background images."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

from apps.api.ppt_rendering.errors import PptRenderingError
from apps.api.ppt_rendering.models import BackgroundImage

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SOF_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}
_MAX_IMAGE_PIXELS = 20_000_000


@dataclass(frozen=True)
class ImageInfo:
    width: int
    height: int


def inspect_background(background: BackgroundImage) -> ImageInfo:
    try:
        info = (
            _inspect_png(background.content)
            if background.media_type == "image/png"
            else _inspect_jpeg(background.content)
        )
    except (IndexError, struct.error, zlib.error) as exc:
        raise _invalid_image() from exc
    if info.width * 9 != info.height * 16:
        raise PptRenderingError(
            "PPT_BACKGROUND_ASPECT_RATIO_INVALID", "background image must be exactly 16:9"
        )
    if info.width < 16 or info.height < 9 or info.width * info.height > _MAX_IMAGE_PIXELS:
        raise PptRenderingError(
            "PPT_BACKGROUND_DIMENSIONS_INVALID", "background dimensions are outside limits"
        )
    return info


def _inspect_png(data: bytes) -> ImageInfo:
    if not data.startswith(_PNG_SIGNATURE):
        raise _invalid_image()
    offset = len(_PNG_SIGNATURE)
    info: ImageInfo | None = None
    channels = 0
    compressed = bytearray()
    first_chunk = True
    kind = b""
    while offset < len(data):
        if offset + 12 > len(data):
            raise _invalid_image()
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        chunk_end = payload_end + 4
        if chunk_end > len(data):
            raise _invalid_image()
        payload = data[payload_start:payload_end]
        expected_crc = struct.unpack_from(">I", data, payload_end)[0]
        if zlib.crc32(kind + payload) != expected_crc:
            raise _invalid_image()
        if first_chunk and kind != b"IHDR":
            raise _invalid_image()
        first_chunk = False
        if kind == b"IHDR":
            if info is not None or length != 13:
                raise _invalid_image()
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            encoding = (compression, filtering, interlace)
            if depth != 8 or color not in {2, 6} or encoding != (0, 0, 0):
                raise _invalid_image()
            info = ImageInfo(width=width, height=height)
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            if length != 0 or chunk_end != len(data):
                raise _invalid_image()
            break
        offset = chunk_end
    if info is None or not compressed or kind != b"IEND":
        raise _invalid_image()
    _validate_png_pixels(bytes(compressed), info, channels)
    return info


def _validate_png_pixels(compressed: bytes, info: ImageInfo, channels: int) -> None:
    if info.width <= 0 or info.height <= 0 or info.width * info.height > _MAX_IMAGE_PIXELS:
        raise PptRenderingError(
            "PPT_BACKGROUND_DIMENSIONS_INVALID", "background dimensions are outside limits"
        )
    expected_row = info.width * channels + 1
    expected_size = expected_row * info.height
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(compressed, expected_size + 1)
    if decoder.unconsumed_tail or len(pixels) > expected_size:
        raise _invalid_image()
    pixels += decoder.flush()
    if not decoder.eof or decoder.unused_data or len(pixels) != expected_size:
        raise _invalid_image()
    if any(pixels[row * expected_row] > 4 for row in range(info.height)):
        raise _invalid_image()


def _inspect_jpeg(data: bytes) -> ImageInfo:
    if len(data) < 6 or not data.startswith(b"\xff\xd8"):
        raise _invalid_image()
    offset = 2
    info: ImageInfo | None = None
    while offset < len(data):
        marker, offset = _next_jpeg_marker(data, offset)
        if marker == 0xD9:
            if offset != len(data) or info is None:
                raise _invalid_image()
            return info
        if marker in {0x01, *range(0xD0, 0xD8)}:
            continue
        if offset + 2 > len(data):
            raise _invalid_image()
        length = struct.unpack_from(">H", data, offset)[0]
        if length < 2 or offset + length > len(data):
            raise _invalid_image()
        segment = data[offset + 2 : offset + length]
        if marker in _JPEG_SOF_MARKERS:
            if info is not None or len(segment) < 6 or segment[0] != 8:
                raise _invalid_image()
            height, width = struct.unpack_from(">HH", segment, 1)
            info = ImageInfo(width=width, height=height)
        offset += length
        if marker == 0xDA:
            return _finish_jpeg_scan(data, offset, info)
    raise _invalid_image()


def _next_jpeg_marker(data: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(data) or data[offset] != 0xFF:
        raise _invalid_image()
    while offset < len(data) and data[offset] == 0xFF:
        offset += 1
    if offset >= len(data) or data[offset] == 0x00:
        raise _invalid_image()
    return data[offset], offset + 1


def _finish_jpeg_scan(data: bytes, offset: int, info: ImageInfo | None) -> ImageInfo:
    if info is None:
        raise _invalid_image()
    while offset < len(data) - 1:
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        if marker == 0x00 or 0xD0 <= marker <= 0xD7:
            offset += 2
            continue
        if marker == 0xFF:
            offset += 1
            continue
        if marker == 0xD9 and offset + 2 == len(data):
            return info
        raise _invalid_image()
    raise _invalid_image()


def _invalid_image() -> PptRenderingError:
    return PptRenderingError(
        "PPT_BACKGROUND_IMAGE_INVALID", "background image is malformed or truncated"
    )
