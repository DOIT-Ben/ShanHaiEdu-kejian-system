"""Small deterministic OOXML writer for editable PPTX documents."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from apps.api.ppt_rendering.models import AssemblyRequest, PageSpec, ShapeElement, TextElement
from apps.api.ppt_rendering.theme import theme_xml

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"


def render_pptx(request: AssemblyRequest) -> bytes:
    files: dict[str, bytes] = {
        "[Content_Types].xml": _content_types(request).encode(),
        "_rels/.rels": _root_rels().encode(),
        "docProps/core.xml": _core_properties().encode(),
        "docProps/app.xml": _app_properties(len(request.pages)).encode(),
        "ppt/presentation.xml": _presentation(request).encode(),
        "ppt/_rels/presentation.xml.rels": _presentation_rels(request).encode(),
        "ppt/presProps.xml": _pres_props().encode(),
        "ppt/viewProps.xml": _view_props().encode(),
        "ppt/tableStyles.xml": _table_styles().encode(),
        "ppt/theme/theme1.xml": theme_xml().encode(),
        "ppt/slideMasters/slideMaster1.xml": _slide_master().encode(),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": _slide_master_rels().encode(),
        "ppt/slideLayouts/slideLayout1.xml": _slide_layout().encode(),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _slide_layout_rels().encode(),
    }
    for position, page in enumerate(request.pages, start=1):
        files[f"ppt/media/image{position}.png"] = page.backgrounds[0].content
        files[f"ppt/slides/slide{position}.xml"] = _slide(page).encode()
        files[f"ppt/slides/_rels/slide{position}.xml.rels"] = _slide_rels(position).encode()

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as package:
        for name in sorted(files):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            info.internal_attr = 0
            info.create_version = 20
            info.extract_version = 20
            info.flag_bits = 0
            package.writestr(info, files[name])
    return output.getvalue()


def _content_types(request: AssemblyRequest) -> str:
    image_defaults = {page.backgrounds[0].media_type for page in request.pages}
    defaults = [
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
    ]
    if "image/png" in image_defaults:
        defaults.append('<Default Extension="png" ContentType="image/png"/>')
    overrides = [
        (
            "/ppt/presentation.xml",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
        ),
        (
            "/ppt/slideMasters/slideMaster1.xml",
            "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml",
        ),
        (
            "/ppt/slideLayouts/slideLayout1.xml",
            "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml",
        ),
        ("/ppt/theme/theme1.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
        (
            "/ppt/presProps.xml",
            "application/vnd.openxmlformats-officedocument.presentationml.presProps+xml",
        ),
        (
            "/ppt/viewProps.xml",
            "application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml",
        ),
        (
            "/ppt/tableStyles.xml",
            "application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml",
        ),
        ("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml"),
        (
            "/docProps/app.xml",
            "application/vnd.openxmlformats-officedocument.extended-properties+xml",
        ),
    ]
    overrides.extend(
        (
            f"/ppt/slides/slide{position}.xml",
            "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        )
        for position in range(1, len(request.pages) + 1)
    )
    return _xml(
        f'<Types xmlns="{_CONTENT}">{"".join(defaults)}'
        + "".join(
            f"<Override PartName={quoteattr(part)} ContentType={quoteattr(content)}/>"
            for part, content in overrides
        )
        + "</Types>"
    )


def _root_rels() -> str:
    return _relationships(
        (
            "rId1",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "ppt/presentation.xml",
        ),
        (
            "rId2",
            "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
            "docProps/core.xml",
        ),
        (
            "rId3",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties",
            "docProps/app.xml",
        ),
    )


def _presentation(request: AssemblyRequest) -> str:
    slide_ids = "".join(
        f'<p:sldId id="{255 + position}" r:id="rId{position + 1}"/>'
        for position in range(1, len(request.pages) + 1)
    )
    return _xml(
        f'<p:presentation xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{slide_ids}</p:sldIdLst>"
        f'<p:sldSz cx="{request.canvas.width}" cy="{request.canvas.height}" type="screen16x9"/>'
        '<p:notesSz cx="6858000" cy="9144000"/><p:defaultTextStyle/></p:presentation>'
    )


def _presentation_rels(request: AssemblyRequest) -> str:
    relationships = [
        (
            "rId1",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster",
            "slideMasters/slideMaster1.xml",
        )
    ]
    relationships.extend(
        (
            f"rId{position + 1}",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
            f"slides/slide{position}.xml",
        )
        for position in range(1, len(request.pages) + 1)
    )
    next_id = len(request.pages) + 2
    relationships.extend(
        (
            f"rId{next_id + offset}",
            kind,
            target,
        )
        for offset, (kind, target) in enumerate(
            (
                (
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps",
                    "presProps.xml",
                ),
                (
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps",
                    "viewProps.xml",
                ),
                (
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles",
                    "tableStyles.xml",
                ),
            )
        )
    )
    return _relationships(*relationships)


def _slide(page: PageSpec) -> str:
    shapes = [_picture_shape()]
    for shape_id, element in enumerate(page.elements, start=3):
        if isinstance(element, TextElement):
            shapes.append(_text_shape(shape_id, element))
        else:
            shapes.append(_native_shape(shape_id, element))
    return _xml(
        f'<p:sld xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}"><p:cSld><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f"{''.join(shapes)}</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def _picture_shape() -> str:
    return (
        '<p:pic><p:nvPicPr><p:cNvPr id="2" name="Background"/><p:cNvPicPr/>'
        '<p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/>'
        '</a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="0" y="0"/>'
        '<a:ext cx="12192000" cy="6858000"/></a:xfrm><a:prstGeom prst="rect">'
        "<a:avLst/></a:prstGeom></p:spPr></p:pic>"
    )


def _text_shape(shape_id: int, element: TextElement) -> str:
    box = element.box
    font = element.font
    align = {"left": "l", "center": "ctr", "right": "r"}[font.align]
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name={quoteattr(element.element_key)}/>'
        '<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
        f'<a:xfrm><a:off x="{box.x}" y="{box.y}"/><a:ext cx="{box.width}" cy="{box.height}"/>'
        '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/>'
        '<a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square"/>'
        f'<a:lstStyle/><a:p><a:pPr algn="{align}"/><a:r><a:rPr lang="zh-CN" '
        f'sz="{font.size_points * 100}" b="{int(font.bold)}" i="{int(font.italic)}">'
        f'<a:solidFill><a:srgbClr val="{font.color}"/></a:solidFill>'
        f"<a:latin typeface={quoteattr(font.family)}/><a:ea typeface={quoteattr(font.family)}/>"
        f'</a:rPr><a:t>{escape(element.text)}</a:t></a:r><a:endParaRPr lang="zh-CN"/>'
        "</a:p></p:txBody></p:sp>"
    )


def _native_shape(shape_id: int, element: ShapeElement) -> str:
    box = element.box
    preset = {
        "rectangle": "rect",
        "ellipse": "ellipse",
        "line": "line",
        "arrow": "line",
    }[element.kind]
    fill = (
        f'<a:solidFill><a:srgbClr val="{element.fill_color}"/></a:solidFill>'
        if element.fill_color is not None and element.kind not in {"line", "arrow"}
        else "<a:noFill/>"
    )
    arrow = '<a:headEnd type="triangle"/>' if element.kind == "arrow" else ""
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name={quoteattr(element.element_key)}/>'
        "<p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>"
        f'<a:xfrm><a:off x="{box.x}" y="{box.y}"/><a:ext cx="{box.width}" cy="{box.height}"/>'
        f'</a:xfrm><a:prstGeom prst="{preset}"><a:avLst/></a:prstGeom>{fill}'
        f'<a:ln w="{element.line_width_points * 12700}"><a:solidFill>'
        f'<a:srgbClr val="{element.line_color}"/></a:solidFill>{arrow}</a:ln></p:spPr></p:sp>'
    )


def _slide_rels(position: int) -> str:
    return _relationships(
        (
            "rId1",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
            f"../media/image{position}.png",
        ),
        (
            "rId2",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout",
            "../slideLayouts/slideLayout1.xml",
        ),
    )


def _slide_master() -> str:
    return _xml(
        f'<p:sldMaster xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}"><p:cSld><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        '</p:spTree></p:cSld><p:clrMap accent1="accent1" accent2="accent2" '
        'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" '
        'bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
        "<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>"
    )


def _slide_layout() -> str:
    return _xml(
        f'<p:sldLayout xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}" type="blank">'
        '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
        "<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>"
        '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
        '<a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>'
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
    )


def _slide_master_rels() -> str:
    return _relationships(
        (
            "rId1",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout",
            "../slideLayouts/slideLayout1.xml",
        ),
        (
            "rId2",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme",
            "../theme/theme1.xml",
        ),
    )


def _slide_layout_rels() -> str:
    return _relationships(
        (
            "rId1",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster",
            "../slideMasters/slideMaster1.xml",
        )
    )


def _relationships(*items: tuple[str, str, str]) -> str:
    body = "".join(
        f"<Relationship Id={quoteattr(rel_id)} Type={quoteattr(kind)} Target={quoteattr(target)}/>"
        for rel_id, kind, target in items
    )
    return _xml(f'<Relationships xmlns="{_REL}">{body}</Relationships>')


def _core_properties() -> str:
    return _xml(
        "<cp:coreProperties "
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>ShanHaiEdu Editable Courseware</dc:title><dc:creator>ShanHaiEdu</dc:creator>"
        "<cp:lastModifiedBy>ShanHaiEdu</cp:lastModifiedBy>"
        '<dcterms:created xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:created>'
        '<dcterms:modified xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _app_properties(slides: int) -> str:
    return _xml(
        "<Properties "
        'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        f"<Application>ShanHaiEdu</Application><PresentationFormat>Widescreen</PresentationFormat>"
        f"<Slides>{slides}</Slides><Notes>0</Notes><HiddenSlides>0</HiddenSlides>"
        "<ScaleCrop>false</ScaleCrop><Company>ShanHaiEdu</Company><AppVersion>1.0</AppVersion>"
        "</Properties>"
    )


def _pres_props() -> str:
    return _xml(f'<p:presentationPr xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}"/>')


def _view_props() -> str:
    return _xml(
        f'<p:viewPr xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}" lastView="sldView">'
        '<p:normalViewPr/><p:slideViewPr><p:cSldViewPr><p:cViewPr varScale="1">'
        '<p:scale><a:sx n="100" d="100"/><a:sy n="100" d="100"/></p:scale>'
        '<p:origin x="0" y="0"/></p:cViewPr><p:guideLst/></p:cSldViewPr></p:slideViewPr>'
        '<p:notesTextViewPr><p:cViewPr><p:scale><a:sx n="100" d="100"/>'
        '<a:sy n="100" d="100"/></p:scale><p:origin x="0" y="0"/></p:cViewPr></p:notesTextViewPr>'
        '<p:gridSpacing cx="72008" cy="72008"/></p:viewPr>'
    )


def _table_styles() -> str:
    return _xml(f'<a:tblStyleLst xmlns:a="{_A}" def="{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}"/>')


def _xml(body: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + body
