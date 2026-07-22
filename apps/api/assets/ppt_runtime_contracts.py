"""Immutable asset facts exchanged with the deterministic PPT runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import cast
from uuid import UUID


class PptAssetPortError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class PptBackgroundFact:
    page_key: str
    position: int
    slot_key: str
    binding_id: UUID
    file_asset_id: UUID
    file_asset_version_id: UUID
    storage_bucket: str
    storage_key: str
    mime_type: str
    size_bytes: int
    sha256: str
    width: int
    height: int

    def snapshot(self) -> dict[str, object]:
        value = asdict(self)
        for key in ("binding_id", "file_asset_id", "file_asset_version_id"):
            value[key] = str(value[key])
        return cast(dict[str, object], value)

    @classmethod
    def from_snapshot(cls, value: Mapping[str, object]) -> PptBackgroundFact:
        try:
            return cls(
                page_key=_text(value.get("page_key")),
                position=_positive_int(value.get("position")),
                slot_key=_text(value.get("slot_key")),
                binding_id=UUID(_text(value.get("binding_id"))),
                file_asset_id=UUID(_text(value.get("file_asset_id"))),
                file_asset_version_id=UUID(_text(value.get("file_asset_version_id"))),
                storage_bucket=_text(value.get("storage_bucket")),
                storage_key=_text(value.get("storage_key")),
                mime_type=_text(value.get("mime_type")),
                size_bytes=_positive_int(value.get("size_bytes")),
                sha256=_sha256(value.get("sha256")),
                width=_positive_int(value.get("width")),
                height=_positive_int(value.get("height")),
            )
        except (TypeError, ValueError) as exc:
            raise PptAssetPortError(
                "PPT_RUNTIME_FROZEN_BACKGROUND_INVALID",
                "a frozen PPT background fact is invalid",
            ) from exc


@dataclass(frozen=True, slots=True)
class PublishedPptxObject:
    bucket: str
    key: str
    etag: str
    mime_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class PptxFileVersionFact:
    file_asset_id: UUID
    file_asset_version_id: UUID
    bucket: str
    key: str
    etag: str
    mime_type: str
    size_bytes: int
    sha256: str
    page_count: int


def _text(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("text value is required")
    return value


def _positive_int(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("positive integer is required")
    return value


def _sha256(value: object) -> str:
    text = _text(value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError("sha256 is invalid")
    return text
