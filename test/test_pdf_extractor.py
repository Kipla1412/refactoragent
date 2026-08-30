import io

import pytest

from utils.pdf_extractor import PDFDocumentExtractor


def _make_pdf(text: str) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_extract_text_returns_content():
    extractor = PDFDocumentExtractor()
    pdf_bytes = _make_pdf("Patient has a fever.")
    text = extractor.extract_text(pdf_bytes)
    assert "Patient has a fever." in text


def test_extract_empty_bytes_raises():
    extractor = PDFDocumentExtractor()
    with pytest.raises(ValueError):
        extractor.extract_text(b"")


def test_extract_invalid_pdf_raises():
    extractor = PDFDocumentExtractor()
    with pytest.raises(ValueError):
        extractor.extract_text(b"not a real pdf")


def test_render_pages_returns_image():
    extractor = PDFDocumentExtractor()
    pdf_bytes = _make_pdf("Patient has a fever.")
    images = extractor.render_pages(pdf_bytes)
    assert len(images) == 1
    assert images[0][:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


def test_render_pages_invalid_pdf_raises():
    extractor = PDFDocumentExtractor()
    with pytest.raises(ValueError):
        extractor.render_pages(b"not a real pdf")

