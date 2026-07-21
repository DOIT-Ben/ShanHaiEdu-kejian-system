from __future__ import annotations

import hashlib
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

from apps.api.ppt_rendering import assemble_pages, export_pptx
from tests.unit.ppt_rendering.helpers import make_page, make_request

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


def test_canonical_replay_is_deterministic() -> None:
    request = make_request(
        pages=(
            make_page(page_key="page-1", position=1),
            make_page(page_key="page-2", position=2),
        )
    )

    first_manifest = assemble_pages(request)
    second_manifest = assemble_pages(request)
    first_export = export_pptx(request)
    second_export = export_pptx(request)

    assert first_manifest == second_manifest
    assert first_manifest.content_hash == second_manifest.content_hash
    assert first_export.content == second_export.content
    assert first_export.sha256 == hashlib.sha256(first_export.content).hexdigest()
    assert first_export.size_bytes == len(first_export.content)
    assert first_export.media_type == (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )


def test_export_contains_one_full_slide_background_and_editable_native_objects() -> None:
    result = export_pptx(make_request())

    with ZipFile(BytesIO(result.content)) as package:
        slide = ElementTree.fromstring(package.read("ppt/slides/slide1.xml"))
        pictures = slide.findall(".//p:pic", NS)
        assert len(pictures) == 1
        offset = pictures[0].find(".//a:off", NS)
        extent = pictures[0].find(".//a:ext", NS)
        assert offset is not None and offset.attrib == {"x": "0", "y": "0"}
        assert extent is not None and extent.attrib == {"cx": "12192000", "cy": "6858000"}

        text_values = [item.text for item in slide.findall(".//a:t", NS)]
        assert {"认识百分数", "把整体平均分成100份。", "25%", "25% = 25 / 100"} <= set(text_values)
        assert len(slide.findall(".//p:sp", NS)) == 5
        assert slide.find(".//a:prstGeom[@prst='ellipse']", NS) is not None
        assert package.read("ppt/media/image1.png").startswith(b"\x89PNG")


def test_formula_manifest_declares_editable_text_fallback() -> None:
    manifest = assemble_pages(make_request())

    formula = next(
        element for element in manifest.pages[0].elements if element.element_key == "page-1-formula"
    )
    assert formula.kind == "formula"
    assert formula.editability == "editable_text_fallback"


def test_export_escapes_user_text_and_all_xml_parts_are_well_formed() -> None:
    source = make_page()
    special = source.elements[0].model_copy(
        update={"element_key": 'title-"quoted"', "text": "比较 25% < 1/2 & 为什么?"}
    )
    page = source.model_copy(update={"elements": (special, *source.elements[1:])})
    result = export_pptx(make_request(pages=(page,)))

    with ZipFile(BytesIO(result.content)) as package:
        xml_names = [name for name in package.namelist() if name.endswith((".xml", ".rels"))]
        for name in xml_names:
            ElementTree.fromstring(package.read(name))
        slide = ElementTree.fromstring(package.read("ppt/slides/slide1.xml"))
        assert "比较 25% < 1/2 & 为什么?" in [item.text for item in slide.findall(".//a:t", NS)]
