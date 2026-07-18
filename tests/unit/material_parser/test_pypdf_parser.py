from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from apps.api.assets.material_parser import MaterialParserError, MaterialParseSource, ParseLimits
from apps.api.assets.pypdf_parser import PypdfMaterialParser
from apps.api.ids import new_uuid7


def two_page_text_pdf() -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)  # pyright: ignore[reportPrivateUsage]
    for text in ("First block", "Second block"):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
        )
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(  # pyright: ignore[reportPrivateUsage]
            content
        )
    writer.write(output)
    return output.getvalue()


def test_pypdf_text_block_limit_applies_to_the_whole_document(tmp_path: Path) -> None:
    payload = two_page_text_pdf()
    path = tmp_path / "two-pages.pdf"
    path.write_bytes(payload)
    source = MaterialParseSource(
        file_asset_version_id=new_uuid7(),
        sha256=hashlib.sha256(payload).hexdigest(),
        mime_type="application/pdf",
        byte_size=len(payload),
    )

    with pytest.raises(MaterialParserError) as error:
        PypdfMaterialParser().parse(
            path,
            source,
            ParseLimits(max_text_blocks=1),
        )

    assert error.value.code == "PDF_TEXT_BLOCK_LIMIT_EXCEEDED"
