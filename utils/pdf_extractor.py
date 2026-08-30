from __future__ import annotations

import io

import pymupdf
from pypdf import PdfReader


class PDFDocumentExtractor:
    """Extract text and render page images from PDF bytes.

    This class contains no agent, OCR, or LLM logic. Rendering pages to
    images is provided so an OCR implementation can consume them when a
    PDF has no embedded text layer.
    """

    def extract_text(self, pdf_bytes: bytes) -> str:
        if not pdf_bytes:
            raise ValueError("PDF bytes are empty.")

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as exc:
            raise ValueError(f"Invalid PDF: {exc}") from exc

        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()

    def render_pages(self, pdf_bytes: bytes) -> list[bytes]:
        """Render every page to a PNG image (for OCR of scanned/image PDFs)."""
        if not pdf_bytes:
            raise ValueError("PDF bytes are empty.")

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise ValueError(f"Invalid PDF: {exc}") from exc

        images: list[bytes] = []
        try:
            for page in doc:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                images.append(pix.tobytes("png"))
        finally:
            doc.close()

        if not images:
            raise ValueError("No pages found in the PDF.")

        return images
