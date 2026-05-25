"""Parse various document formats into plain text."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentParser:
    """Parse various document formats into plain text."""

    SUPPORTED_EXTENSIONS: set[str] = {".txt", ".md", ".pdf", ".docx"}

    async def parse(self, file_path: str) -> str:
        """Parse a file and return its text content.

        Supports:
        - .txt / .md: read as UTF-8 text
        - .pdf: extract text using PyMuPDF (fitz) if available, else raise ValueError
        - .docx: extract text using python-docx if available, else raise ValueError

        For unsupported formats or parsing failures, raise ValueError.
        Logs warnings when optional dependencies are missing.
        """
        ext = Path(file_path).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '{ext}'. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        try:
            if ext in {".txt", ".md"}:
                return self._parse_text(file_path)
            elif ext == ".pdf":
                return self._parse_pdf(file_path)
            elif ext == ".docx":
                return self._parse_docx(file_path)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(
                f"Failed to parse '{file_path}': {exc}"
            ) from exc

    @staticmethod
    def _parse_text(file_path: str) -> str:
        """Read a plain text or markdown file as UTF-8."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _parse_pdf(file_path: str) -> str:
        """Extract text from a PDF file using PyMuPDF (fitz)."""
        try:
            import fitz  # type: ignore[import-untyped]
        except ImportError:
            logger.warning(
                "PyMuPDF (fitz) is not installed. "
                "Install it with: pip install pymupdf"
            )
            raise ValueError(
                "PyMuPDF is required to parse PDF files. Install: pip install pymupdf"
            )

        text_parts: list[str] = []
        with fitz.open(file_path) as doc:
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(page_text)
                else:
                    logger.debug("Page %d yielded no text in PDF %s", page_num, file_path)

        if not text_parts:
            logger.warning("No extractable text found in PDF: %s", file_path)

        return "\n\n".join(text_parts)

    @staticmethod
    def _parse_docx(file_path: str) -> str:
        """Extract text from a DOCX file using python-docx."""
        try:
            from docx import Document  # type: ignore[import-untyped]
        except ImportError:
            logger.warning(
                "python-docx is not installed. "
                "Install it with: pip install python-docx"
            )
            raise ValueError(
                "python-docx is required to parse DOCX files. "
                "Install: pip install python-docx"
            )

        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

        if not paragraphs:
            logger.warning("No extractable text found in DOCX: %s", file_path)

        return "\n\n".join(paragraphs)
