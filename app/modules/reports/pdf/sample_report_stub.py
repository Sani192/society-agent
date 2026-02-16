from __future__ import annotations


def generate_sample_report_pdf() -> bytes:
    """Return minimal static PDF bytes for quick WhatsApp report plumbing tests."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 72>>stream\n"
        b"BT /F1 14 Tf 20 100 Td (Sample Report PDF - WhatsApp Flow) Tj ET\n"
        b"endstream endobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000061 00000 n \n"
        b"0000000118 00000 n \n0000000249 00000 n \n0000000371 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n441\n%%EOF\n"
    )
