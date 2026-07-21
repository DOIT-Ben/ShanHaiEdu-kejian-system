from __future__ import annotations

import hashlib
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from apps.api.ppt_rendering import FontStyle, ShapeElement, assemble_pages, export_pptx, ooxml
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


def test_zip_metadata_is_cross_platform_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    real_zip_info = ooxml.ZipInfo

    def export_with_platform_default(create_system: int) -> tuple[bytes, str]:
        def platform_zip_info(*args: object, **kwargs: object) -> object:
            info = real_zip_info(*args, **kwargs)  # type: ignore[arg-type]
            info.create_system = create_system
            info.external_attr = (0o100666 if create_system == 0 else 0o100644) << 16
            info.internal_attr = create_system
            info.create_version = 63
            info.extract_version = 10
            info.flag_bits = 0x800
            return info

        monkeypatch.setattr(ooxml, "ZipInfo", platform_zip_info)
        result = export_pptx(make_request())
        return result.content, result.sha256

    windows_content, windows_hash = export_with_platform_default(0)
    unix_content, unix_hash = export_with_platform_default(3)

    assert windows_content == unix_content
    assert windows_hash == unix_hash
    with ZipFile(BytesIO(unix_content)) as package:
        for entry in package.infolist():
            assert entry.create_system == 3
            assert entry.external_attr == 0o100600 << 16
            assert entry.internal_attr == 0
            assert entry.create_version == 20
            assert entry.extract_version == 20
            assert entry.flag_bits == 0


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


def test_theme_format_scheme_has_required_style_counts() -> None:
    result = export_pptx(make_request())

    with ZipFile(BytesIO(result.content)) as package:
        theme = ElementTree.fromstring(package.read("ppt/theme/theme1.xml"))
        format_scheme = theme.find("./a:themeElements/a:fmtScheme", NS)
        assert format_scheme is not None
        for list_name in (
            "fillStyleLst",
            "lnStyleLst",
            "effectStyleLst",
            "bgFillStyleLst",
        ):
            style_list = format_scheme.find(f"./a:{list_name}", NS)
            assert style_list is not None
            assert len(style_list) >= 3


def test_view_properties_use_powerpoint_compatible_minimal_profile() -> None:
    result = export_pptx(make_request())

    with ZipFile(BytesIO(result.content)) as package:
        view_properties = ElementTree.fromstring(package.read("ppt/viewProps.xml"))
        children = list(view_properties)

    assert len(children) == 1
    assert children[0].tag == f"{{{NS['p']}}}gridSpacing"
    assert children[0].attrib == {"cx": "72008", "cy": "72008"}


def test_formula_manifest_declares_editable_text_fallback() -> None:
    manifest = assemble_pages(make_request())

    formula = next(
        element for element in manifest.pages[0].elements if element.element_key == "page-1-formula"
    )
    assert formula.kind == "formula"
    assert formula.editability == "editable_text_fallback"
    assert formula.text == "25% = 25 / 100"
    assert formula.font is not None and formula.font.size_points == 18
    shape = manifest.pages[0].elements[-1]
    assert shape.fill_color == "FFD966"
    assert shape.line_color == "C55A11"
    assert shape.line_width_points == 2


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


@pytest.mark.parametrize(
    "mutation",
    [
        {"text": "修改后的标题"},
        {"font": FontStyle(family="SimSun", size_points=28, bold=True, color="17365D")},
        {"font": FontStyle(size_points=30, bold=True, color="17365D")},
        {"font": FontStyle(size_points=28, bold=False, color="17365D")},
        {"font": FontStyle(size_points=28, bold=True, italic=True, color="17365D")},
        {"font": FontStyle(size_points=28, bold=True, color="FF0000")},
        {"font": FontStyle(size_points=28, bold=True, color="17365D", align="center")},
    ],
)
def test_text_semantic_changes_change_content_hash(mutation: dict[str, object]) -> None:
    source = make_page()
    changed = source.elements[0].model_copy(update=mutation)
    page = source.model_copy(update={"elements": (changed, *source.elements[1:])})

    assert (
        assemble_pages(make_request()).content_hash
        != assemble_pages(make_request(pages=(page,))).content_hash
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {"fill_color": "00FF00"},
        {"line_color": "0000FF"},
        {"line_width_points": 4},
    ],
)
def test_shape_style_changes_change_content_hash(mutation: dict[str, object]) -> None:
    source = make_page()
    changed = source.elements[-1].model_copy(update=mutation)
    page = source.model_copy(update={"elements": (*source.elements[:-1], changed)})

    assert (
        assemble_pages(make_request()).content_hash
        != assemble_pages(make_request(pages=(page,))).content_hash
    )


def test_all_native_shape_geometries_are_valid_drawingml() -> None:
    source = make_page()
    shapes = tuple(
        ShapeElement(
            element_key=kind,
            kind=kind,
            box=source.elements[-1].box,
            fill_color="FFD966" if kind in {"rectangle", "ellipse"} else None,
            line_color="C55A11",
        )
        for kind in ("rectangle", "ellipse", "line", "arrow")
    )
    page = source.model_copy(update={"elements": shapes})

    result = export_pptx(make_request(pages=(page,)))

    with ZipFile(BytesIO(result.content)) as package:
        slide = ElementTree.fromstring(package.read("ppt/slides/slide1.xml"))
        rendered: dict[str, ElementTree.Element] = {}
        for shape in slide.findall(".//p:sp", NS):
            name = shape.find("./p:nvSpPr/p:cNvPr", NS)
            geometry = shape.find("./p:spPr/a:prstGeom", NS)
            assert name is not None and geometry is not None
            rendered[name.attrib["name"]] = shape
        assert rendered["rectangle"].find("./p:spPr/a:prstGeom", NS).attrib["prst"] == "rect"  # type: ignore[union-attr]
        assert rendered["ellipse"].find("./p:spPr/a:prstGeom", NS).attrib["prst"] == "ellipse"  # type: ignore[union-attr]
        assert rendered["line"].find("./p:spPr/a:prstGeom", NS).attrib["prst"] == "line"  # type: ignore[union-attr]
        assert rendered["arrow"].find("./p:spPr/a:prstGeom", NS).attrib["prst"] == "line"  # type: ignore[union-attr]
        assert rendered["line"].find("./p:spPr/a:ln/a:headEnd", NS) is None
        arrow_head = rendered["arrow"].find("./p:spPr/a:ln/a:headEnd", NS)
        assert arrow_head is not None and arrow_head.attrib["type"] == "triangle"
