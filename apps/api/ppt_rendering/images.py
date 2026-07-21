"""Dependency-free validation for the frozen PNG background profile."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

from apps.api.ppt_rendering.errors import PptRenderingError
from apps.api.ppt_rendering.models import BackgroundImage

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_IMAGE_PIXELS = 20_000_000


@dataclass(frozen=True)
class ImageInfo:
    width: int
    height: int


@dataclass
class _PngState:
    info: ImageInfo | None = None
    bit_depth: int = 0
    color_type: int = -1
    bits_per_pixel: int = 0
    palette_entries: int = 0
    compressed: bytearray = field(default_factory=bytearray)
    seen_idat: bool = False
    idat_ended: bool = False
    seen_trns: bool = False
    seen_iend: bool = False


def inspect_background(background: BackgroundImage) -> ImageInfo:
    if background.media_type != "image/png":
        raise PptRenderingError(
            "PPT_BACKGROUND_IMAGE_PROFILE_UNSUPPORTED",
            "the V1 render core accepts only validated PNG backgrounds",
        )
    try:
        info = _inspect_png(background.content)
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
    state = _PngState()
    first_chunk = True
    kind = b""
    while offset < len(data):
        kind, payload, chunk_end = _read_png_chunk(data, offset)
        if first_chunk and kind != b"IHDR":
            raise _invalid_image()
        first_chunk = False
        if _apply_png_chunk(state, kind, payload):
            if chunk_end != len(data):
                raise _invalid_image()
            break
        offset = chunk_end
    if (
        state.info is None
        or not state.compressed
        or kind != b"IEND"
        or not state.seen_iend
        or (state.color_type == 3 and not state.palette_entries)
    ):
        raise _invalid_image()
    _validate_png_pixels(state)
    return state.info


def _read_png_chunk(data: bytes, offset: int) -> tuple[bytes, bytes, int]:
    if offset + 12 > len(data):
        raise _invalid_image()
    length = struct.unpack_from(">I", data, offset)[0]
    kind = data[offset + 4 : offset + 8]
    if len(kind) != 4 or not all(65 <= value <= 90 or 97 <= value <= 122 for value in kind):
        raise _invalid_image()
    if not 65 <= kind[2] <= 90:
        raise _invalid_image()
    payload_start = offset + 8
    payload_end = payload_start + length
    chunk_end = payload_end + 4
    if chunk_end > len(data):
        raise _invalid_image()
    payload = data[payload_start:payload_end]
    expected_crc = struct.unpack_from(">I", data, payload_end)[0]
    if zlib.crc32(kind + payload) != expected_crc:
        raise _invalid_image()
    return kind, payload, chunk_end


def _apply_png_chunk(state: _PngState, kind: bytes, payload: bytes) -> bool:
    if kind == b"IHDR":
        _apply_png_header(state, payload)
    elif kind == b"PLTE":
        _apply_png_palette(state, payload)
    elif kind == b"IDAT":
        _apply_png_data(state, payload)
    elif kind == b"tRNS":
        _apply_png_transparency(state, payload)
    elif kind == b"IEND":
        if payload or state.seen_iend:
            raise _invalid_image()
        state.seen_iend = True
        return True
    elif kind and kind[0] & 0x20 == 0:
        raise _invalid_image()
    if state.seen_idat and kind != b"IDAT":
        state.idat_ended = True
    return False


def _apply_png_header(state: _PngState, payload: bytes) -> None:
    if state.info is not None or len(payload) != 13:
        raise _invalid_image()
    values = struct.unpack(">IIBBBBB", payload)
    width, height, state.bit_depth, state.color_type, compression, filtering, interlace = values
    valid_color = (state.color_type in {2, 6} and state.bit_depth == 8) or (
        state.color_type == 3 and state.bit_depth in {1, 2, 4, 8}
    )
    if not valid_color or (compression, filtering, interlace) != (0, 0, 0):
        raise _invalid_image()
    state.info = ImageInfo(width=width, height=height)
    state.bits_per_pixel = {2: 24, 3: state.bit_depth, 6: 32}[state.color_type]


def _apply_png_palette(state: _PngState, payload: bytes) -> None:
    if (
        state.info is None
        or state.seen_idat
        or state.palette_entries
        or state.seen_trns
        or state.color_type == 6
    ):
        raise _invalid_image()
    if len(payload) < 3 or len(payload) % 3:
        raise _invalid_image()
    state.palette_entries = len(payload) // 3
    if state.palette_entries > 256 or (
        state.color_type == 3 and state.palette_entries > 2**state.bit_depth
    ):
        raise _invalid_image()


def _apply_png_transparency(state: _PngState, payload: bytes) -> None:
    if state.info is None or state.seen_idat or state.seen_trns:
        raise _invalid_image()
    if state.color_type == 3:
        if not state.palette_entries or not 1 <= len(payload) <= state.palette_entries:
            raise _invalid_image()
    elif state.color_type == 2:
        if len(payload) != 6:
            raise _invalid_image()
        if any(value > 2**state.bit_depth - 1 for value in struct.unpack(">HHH", payload)):
            raise _invalid_image()
    else:
        raise _invalid_image()
    state.seen_trns = True


def _apply_png_data(state: _PngState, payload: bytes) -> None:
    if state.info is None or state.idat_ended:
        raise _invalid_image()
    if state.color_type == 3 and not state.palette_entries:
        raise _invalid_image()
    state.seen_idat = True
    state.compressed.extend(payload)


def _validate_png_pixels(state: _PngState) -> None:
    info = state.info
    if info is None or info.width <= 0 or info.height <= 0:
        raise _invalid_image()
    if info.width * info.height > _MAX_IMAGE_PIXELS:
        raise PptRenderingError(
            "PPT_BACKGROUND_DIMENSIONS_INVALID", "background dimensions are outside limits"
        )
    row_size = (info.width * state.bits_per_pixel + 7) // 8
    expected_size = (row_size + 1) * info.height
    pixels = _decompress_png(bytes(state.compressed), expected_size)
    rows = _unfilter_png_rows(pixels, row_size, state.bits_per_pixel, info.height)
    if state.color_type == 3:
        _validate_palette_indices(rows, info.width, state.bit_depth, state.palette_entries)


def _decompress_png(compressed: bytes, expected_size: int) -> bytes:
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(compressed, expected_size + 1)
    if decoder.unconsumed_tail or len(pixels) > expected_size:
        raise _invalid_image()
    pixels += decoder.flush()
    if not decoder.eof or decoder.unused_data or len(pixels) != expected_size:
        raise _invalid_image()
    return pixels


def _unfilter_png_rows(
    pixels: bytes, row_size: int, bits_per_pixel: int, height: int
) -> tuple[bytes, ...]:
    rows: list[bytes] = []
    previous = bytes(row_size)
    filter_bytes = max(1, (bits_per_pixel + 7) // 8)
    stride = row_size + 1
    for row_number in range(height):
        offset = row_number * stride
        filter_type = pixels[offset]
        if filter_type > 4:
            raise _invalid_image()
        raw = pixels[offset + 1 : offset + stride]
        reconstructed = _unfilter_png_row(raw, previous, filter_bytes, filter_type)
        rows.append(reconstructed)
        previous = reconstructed
    return tuple(rows)


def _unfilter_png_row(raw: bytes, previous: bytes, bpp: int, filter_type: int) -> bytes:
    result = bytearray(len(raw))
    for index, value in enumerate(raw):
        left = result[index - bpp] if index >= bpp else 0
        above = previous[index]
        upper_left = previous[index - bpp] if index >= bpp else 0
        predictor = {
            0: 0,
            1: left,
            2: above,
            3: (left + above) // 2,
            4: _paeth(left, above, upper_left),
        }[filter_type]
        result[index] = (value + predictor) & 0xFF
    return bytes(result)


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distances = (
        (abs(estimate - left), left),
        (abs(estimate - above), above),
        (abs(estimate - upper_left), upper_left),
    )
    return min(distances, key=lambda item: item[0])[1]


def _validate_palette_indices(
    rows: tuple[bytes, ...], width: int, bit_depth: int, palette_entries: int
) -> None:
    mask = (1 << bit_depth) - 1
    for row in rows:
        for position in range(width):
            bit_position = position * bit_depth
            shift = 8 - bit_depth - bit_position % 8
            palette_index = (row[bit_position // 8] >> shift) & mask
            if palette_index >= palette_entries:
                raise _invalid_image()


def _invalid_image() -> PptRenderingError:
    return PptRenderingError(
        "PPT_BACKGROUND_IMAGE_INVALID", "background PNG is malformed or truncated"
    )
