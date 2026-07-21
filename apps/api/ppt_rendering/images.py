"""Dependency-free structural validation for supported background images."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field

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


@dataclass(frozen=True)
class _JpegFrame:
    info: ImageInfo
    component_ids: tuple[int, ...]
    quantization_ids: tuple[int, ...]


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
        or (state.color_type == 3 and not state.palette_entries)
    ):
        raise _invalid_image()
    _validate_png_pixels(bytes(state.compressed), state.info, state.bits_per_pixel)
    return state.info


def _read_png_chunk(data: bytes, offset: int) -> tuple[bytes, bytes, int]:
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
    return kind, payload, chunk_end


def _apply_png_chunk(state: _PngState, kind: bytes, payload: bytes) -> bool:
    if kind == b"IHDR":
        _apply_png_header(state, payload)
    elif kind == b"PLTE":
        _apply_png_palette(state, payload)
    elif kind == b"IDAT":
        if state.info is None or state.idat_ended:
            raise _invalid_image()
        if state.color_type == 3 and not state.palette_entries:
            raise _invalid_image()
        state.seen_idat = True
        state.compressed.extend(payload)
    elif kind == b"tRNS":
        if state.seen_idat or state.color_type != 3 or not state.palette_entries:
            raise _invalid_image()
        if len(payload) > state.palette_entries:
            raise _invalid_image()
    elif kind == b"IEND":
        if payload:
            raise _invalid_image()
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
    if state.info is None or state.seen_idat or state.palette_entries:
        raise _invalid_image()
    if len(payload) < 3 or len(payload) % 3:
        raise _invalid_image()
    state.palette_entries = len(payload) // 3
    if state.palette_entries > 256 or (
        state.color_type == 3 and state.palette_entries > 2**state.bit_depth
    ):
        raise _invalid_image()


def _validate_png_pixels(compressed: bytes, info: ImageInfo, bits_per_pixel: int) -> None:
    if info.width <= 0 or info.height <= 0 or info.width * info.height > _MAX_IMAGE_PIXELS:
        raise PptRenderingError(
            "PPT_BACKGROUND_DIMENSIONS_INVALID", "background dimensions are outside limits"
        )
    expected_row = (info.width * bits_per_pixel + 7) // 8 + 1
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
    frame: _JpegFrame | None = None
    quantization_tables: set[int] = set()
    dc_tables: set[int] = set()
    ac_tables: set[int] = set()
    while offset < len(data):
        marker, offset = _next_jpeg_marker(data, offset)
        if marker == 0x01:
            continue
        if marker in {0xD8, 0xD9, *range(0xD0, 0xD8)}:
            raise _invalid_image()
        if offset + 2 > len(data):
            raise _invalid_image()
        length = struct.unpack_from(">H", data, offset)[0]
        if length < 2 or offset + length > len(data):
            raise _invalid_image()
        segment = data[offset + 2 : offset + length]
        if marker in _JPEG_SOF_MARKERS:
            if marker != 0xC0 or frame is not None:
                raise _invalid_image()
            frame = _parse_jpeg_frame(segment)
        elif marker == 0xDB:
            quantization_tables.update(_parse_quantization_tables(segment))
        elif marker == 0xC4:
            segment_dc, segment_ac = _parse_huffman_tables(segment)
            dc_tables.update(segment_dc)
            ac_tables.update(segment_ac)
        offset += length
        if marker == 0xDA:
            _validate_jpeg_scan_header(segment, frame, quantization_tables, dc_tables, ac_tables)
            return _finish_jpeg_scan(data, offset, frame)
    raise _invalid_image()


def _parse_jpeg_frame(segment: bytes) -> _JpegFrame:
    if len(segment) < 6 or segment[0] != 8:
        raise _invalid_image()
    height, width = struct.unpack_from(">HH", segment, 1)
    component_count = segment[5]
    if component_count not in {1, 3} or len(segment) != 6 + component_count * 3:
        raise _invalid_image()
    component_ids: list[int] = []
    quantization_ids: list[int] = []
    for position in range(component_count):
        component_id, sampling, table_id = segment[6 + position * 3 : 9 + position * 3]
        horizontal, vertical = sampling >> 4, sampling & 0x0F
        if (
            component_id in component_ids
            or not 1 <= horizontal <= 4
            or not 1 <= vertical <= 4
            or table_id > 3
        ):
            raise _invalid_image()
        component_ids.append(component_id)
        quantization_ids.append(table_id)
    return _JpegFrame(
        info=ImageInfo(width=width, height=height),
        component_ids=tuple(component_ids),
        quantization_ids=tuple(quantization_ids),
    )


def _parse_quantization_tables(segment: bytes) -> set[int]:
    table_ids: set[int] = set()
    offset = 0
    while offset < len(segment):
        descriptor = segment[offset]
        precision, table_id = descriptor >> 4, descriptor & 0x0F
        table_size = 64 * (2 if precision else 1)
        end = offset + 1 + table_size
        if precision not in {0, 1} or table_id > 3 or end > len(segment):
            raise _invalid_image()
        values = segment[offset + 1 : end]
        if table_id in table_ids or _quantization_has_zero(values, precision):
            raise _invalid_image()
        table_ids.add(table_id)
        offset = end
    if not table_ids:
        raise _invalid_image()
    return table_ids


def _quantization_has_zero(values: bytes, precision: int) -> bool:
    if precision == 0:
        return 0 in values
    return any(struct.unpack_from(">H", values, offset)[0] == 0 for offset in range(0, 128, 2))


def _parse_huffman_tables(segment: bytes) -> tuple[set[int], set[int]]:
    dc_tables: set[int] = set()
    ac_tables: set[int] = set()
    offset = 0
    while offset < len(segment):
        if offset + 17 > len(segment):
            raise _invalid_image()
        descriptor = segment[offset]
        table_class, table_id = descriptor >> 4, descriptor & 0x0F
        symbol_count = sum(segment[offset + 1 : offset + 17])
        end = offset + 17 + symbol_count
        target = dc_tables if table_class == 0 else ac_tables
        if table_class not in {0, 1} or table_id > 3 or not symbol_count or end > len(segment):
            raise _invalid_image()
        if table_id in target:
            raise _invalid_image()
        target.add(table_id)
        offset = end
    return dc_tables, ac_tables


def _validate_jpeg_scan_header(
    segment: bytes,
    frame: _JpegFrame | None,
    quantization_tables: set[int],
    dc_tables: set[int],
    ac_tables: set[int],
) -> None:
    if frame is None or not segment:
        raise _invalid_image()
    component_count = segment[0]
    if component_count != len(frame.component_ids) or len(segment) != 1 + component_count * 2 + 3:
        raise _invalid_image()
    selectors: list[int] = []
    for position in range(component_count):
        component_id, tables = segment[1 + position * 2 : 3 + position * 2]
        dc_table, ac_table = tables >> 4, tables & 0x0F
        if component_id in selectors or dc_table not in dc_tables or ac_table not in ac_tables:
            raise _invalid_image()
        selectors.append(component_id)
    if set(selectors) != set(frame.component_ids):
        raise _invalid_image()
    if not set(frame.quantization_ids) <= quantization_tables or segment[-3:] != b"\x00\x3f\x00":
        raise _invalid_image()


def _next_jpeg_marker(data: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(data) or data[offset] != 0xFF:
        raise _invalid_image()
    while offset < len(data) and data[offset] == 0xFF:
        offset += 1
    if offset >= len(data) or data[offset] == 0x00:
        raise _invalid_image()
    return data[offset], offset + 1


def _finish_jpeg_scan(data: bytes, offset: int, frame: _JpegFrame | None) -> ImageInfo:
    if frame is None:
        raise _invalid_image()
    entropy_bytes = 0
    while offset < len(data) - 1:
        if data[offset] != 0xFF:
            entropy_bytes += 1
            offset += 1
            continue
        marker = data[offset + 1]
        if marker == 0x00:
            entropy_bytes += 1
            offset += 2
            continue
        if 0xD0 <= marker <= 0xD7:
            offset += 2
            continue
        if marker == 0xFF:
            offset += 1
            continue
        if marker == 0xD9 and offset + 2 == len(data) and entropy_bytes:
            return frame.info
        raise _invalid_image()
    raise _invalid_image()


def _invalid_image() -> PptRenderingError:
    return PptRenderingError(
        "PPT_BACKGROUND_IMAGE_INVALID", "background image is malformed or truncated"
    )
