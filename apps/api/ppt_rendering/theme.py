"""Static DrawingML theme used by the pure PPTX writer."""

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def theme_xml() -> str:
    body = (
        f'<a:theme xmlns:a="{_A}" name="ShanHaiEdu"><a:themeElements>'
        '<a:clrScheme name="Office">'
        '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
        '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="17365D"/></a:dk2>'
        '<a:lt2><a:srgbClr val="F2F2F2"/></a:lt2>'
        '<a:accent1><a:srgbClr val="4472C4"/></a:accent1>'
        '<a:accent2><a:srgbClr val="ED7D31"/></a:accent2>'
        '<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>'
        '<a:accent4><a:srgbClr val="FFC000"/></a:accent4>'
        '<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5>'
        '<a:accent6><a:srgbClr val="70AD47"/></a:accent6>'
        '<a:hlink><a:srgbClr val="0563C1"/></a:hlink>'
        '<a:folHlink><a:srgbClr val="954F72"/></a:folHlink>'
        '</a:clrScheme><a:fontScheme name="Office"><a:majorFont>'
        '<a:latin typeface="Aptos Display"/><a:ea typeface="Microsoft YaHei"/>'
        '<a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/>'
        '<a:ea typeface="Microsoft YaHei"/><a:cs typeface=""/></a:minorFont>'
        '</a:fontScheme><a:fmtScheme name="Office"><a:fillStyleLst>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
        '<a:lnStyleLst><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/>'
        "</a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle>"
        "<a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst>"
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>'
        "</a:fmtScheme></a:themeElements></a:theme>"
    )
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + body
