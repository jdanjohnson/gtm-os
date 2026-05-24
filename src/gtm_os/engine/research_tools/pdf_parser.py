"""PDF parser tool — extract and search text from PDF reports.

Inspired by PraisonAI's PDFSearchTool. Extracts text from PDF files
for prospect research, report analysis, and data extraction.

Uses a lightweight approach: tries PyMuPDF (fitz) first, falls back to
a basic binary text extraction if the library isn't installed.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PDFParserTool:
    """Extract and search text from PDF files."""

    def extract(self, file_path: str) -> dict[str, Any]:
        """Extract all text from a PDF file."""
        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}
        if path.suffix.lower() != ".pdf":
            return {"ok": False, "error": f"Not a PDF file: {file_path}"}

        try:
            text = _extract_with_pymupdf(path)
        except ImportError:
            logger.info("PyMuPDF not installed, using basic text extraction")
            text = _extract_basic(path)
        except Exception as e:
            return {"ok": False, "error": f"PDF extraction failed: {e}"}

        return {
            "ok": True,
            "file": file_path,
            "text": text[:15000],
            "char_count": len(text),
            "page_count": text.count("--- Page "),
        }

    def search(
        self,
        file_path: str,
        query: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search a PDF for paragraphs matching a query."""
        result = self.extract(file_path)
        if not result["ok"]:
            return result
        text = result["text"]
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        query_lower = query.lower()
        matches = []
        for para in paragraphs:
            if query_lower in para.lower():
                matches.append(para[:500])
            if len(matches) >= limit:
                break
        return {
            "ok": True,
            "query": query,
            "match_count": len(matches),
            "matches": matches,
        }


def _extract_with_pymupdf(path: Path) -> str:
    """Extract text using PyMuPDF (fitz)."""
    import fitz  # type: ignore[import-untyped]

    doc = fitz.open(str(path))
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        pages.append(f"--- Page {i + 1} ---\n{text}")
    doc.close()
    return "\n\n".join(pages)


def _extract_basic(path: Path) -> str:
    """Fallback: extract readable text from PDF binary.

    This is a very basic approach that finds text strings in the PDF
    binary. It won't handle all PDFs but works for simple text-based ones.
    """
    raw = path.read_bytes()
    text_chunks: list[str] = []

    # Extract text between BT/ET markers (PDF text objects).
    for match in re.finditer(rb"BT\s(.*?)\sET", raw, re.DOTALL):
        block = match.group(1)
        # Extract string literals in parentheses.
        for s in re.finditer(rb"\(([^)]*)\)", block):
            decoded = s.group(1).decode("latin-1", errors="replace")
            if len(decoded.strip()) > 1:
                text_chunks.append(decoded)

    if not text_chunks:
        # Last resort: extract any printable ASCII sequences.
        for match in re.finditer(rb"[\x20-\x7e]{10,}", raw):
            text_chunks.append(match.group().decode("ascii", errors="replace"))

    return "\n".join(text_chunks)
