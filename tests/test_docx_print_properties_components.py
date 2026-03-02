from io import BytesIO

from docx import Document

from app.utils.docx_generator import (
    apply_print_properties_to_docx,
    build_docx_from_components,
)


def _minimal_document_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Hello</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>"""


def test_apply_print_properties_to_components_docx_applies_margins_and_page_size():
    base_docx = build_docx_from_components(document_xml=_minimal_document_xml())
    print_props = {
        "margins": {"top": 0.75, "right": 0.6, "bottom": 0.8, "left": 0.65},
        "pageSize": {"width": 8.3, "height": 11.7},
        "lineHeight": 1.5,
    }

    out_docx = apply_print_properties_to_docx(base_docx, print_props)
    doc = Document(BytesIO(out_docx))
    section = doc.sections[0]

    assert abs(section.top_margin.inches - 0.75) < 0.01
    assert abs(section.right_margin.inches - 0.6) < 0.01
    assert abs(section.bottom_margin.inches - 0.8) < 0.01
    assert abs(section.left_margin.inches - 0.65) < 0.01
    assert abs(section.page_width.inches - 8.3) < 0.01
    assert abs(section.page_height.inches - 11.7) < 0.01
