from __future__ import annotations

import io

import pymupdf
from pypdf import PdfReader


class PDFDocumentExtractor:
    """Extract text and render page images from PDF or image bytes.

    This class contains no agent, OCR, or LLM logic. Rendering pages to
    images is provided so an OCR implementation can consume them when a
    PDF has no embedded text layer or when the input is a standalone image.
    """

    @staticmethod
    def is_image(data: bytes) -> bool:
        """Return True when the bytes are a standalone image (not a PDF)."""
        try:
            from PIL import Image

            with Image.open(io.BytesIO(data)) as img:
                img.verify()
            return True
        except Exception:
            return False

    def extract_text(self, pdf_bytes: bytes) -> str:
        if not pdf_bytes:
            raise ValueError("PDF bytes are empty.")

        # Standalone images have no text layer; return empty so the caller
        # routes them through OCR.
        if self.is_image(pdf_bytes):
            return ""

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as exc:
            raise ValueError(f"Invalid PDF: {exc}") from exc

        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()

    def render_pages(self, data: bytes) -> list[bytes]:
        """Render every page to a PNG image (for OCR).

        Works for both scanned/image PDFs and standalone images.
        """
        if not data:
            raise ValueError("File bytes are empty.")

        try:
            doc = pymupdf.open(stream=data)
        except Exception as exc:
            raise ValueError(f"Invalid document: {exc}") from exc

        images: list[bytes] = []
        try:
            for page in doc:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                images.append(pix.tobytes("png"))
        finally:
            doc.close()

        if not images:
            raise ValueError("No pages found in the document.")

        return images
