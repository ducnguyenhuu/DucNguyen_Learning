"""PDF document parser using PyMuPDF (fitz).

Extracts text page-by-page from PDF files, preserving page numbers and
attempting to detect section headings from font-size heuristics.

Edge cases handled
------------------
- **Corrupted / unreadable PDF**: ``fitz.FileDataError`` and any other
  library exception are caught and re-raised as ``ParserError`` so the
  ingestion service can skip the file, log the error, and continue
  (Edge Case §corrupted per spec).
- **Password-protected PDF**: raises ``ParserError`` with a clear message.
- **Image-only pages**: ``page.get_text()`` returns an empty string; the
  page is still included in ``pages`` with empty ``text`` so that page
  count metadata remains accurate.
- **Empty document**: returns a ``ParsedDocument`` with empty ``content``
  (``is_empty == True``); the ingestion service decides whether to skip it.
"""
from __future__ import annotations

import os

import structlog

from app.parsers.base import (
    DocumentParser,
    PageContent,
    ParsedDocument,
    ParserError,
    SectionContent,
)

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Heading-detection heuristic constants
# ---------------------------------------------------------------------------
# PyMuPDF reports font sizes in points.  Pages with a median body font size
# of ~10–12pt commonly use 14pt+ for headings; we use a relative threshold.
_HEADING_FONT_RATIO = 1.2   # font size >= body_size * ratio → heading candidate
_MIN_HEADING_CHARS = 3       # headings shorter than this are noise
_MAX_HEADING_CHARS = 200     # headings longer than this are body text


class PdfParser(DocumentParser):
    """Parse PDF files into :class:`~app.parsers.base.ParsedDocument`.

    Uses PyMuPDF (``import fitz``) for text extraction.  The parser operates
    entirely synchronously inside the ``async parse()`` coroutine; PDF text
    extraction is CPU-bound and completes quickly enough for typical documents.
    For very large PDFs (1000+ pages), consider running this in a thread pool
    executor via ``asyncio.get_event_loop().run_in_executor()``.
    """

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".pdf"})

    async def parse(self, file_path: str) -> ParsedDocument:
        """Extract text from a PDF file.

        Parameters
        ----------
        file_path:
            Absolute path to the ``.pdf`` file.

        Returns
        -------
        ParsedDocument
            Contains per-page ``PageContent`` list, detected section headings
            as ``SectionContent`` list, and the full concatenated ``content``
            string with ``\\n\\n`` page separators.

        Raises
        ------
        ParserError
            If the file is missing, corrupt, password-protected, or otherwise
            unreadable by PyMuPDF.
        """
        try:
            import fitz  # PyMuPDF — imported lazily to keep startup fast
        except ImportError as exc:
            raise ParserError(
                file_path,
                "PyMuPDF (fitz) is not installed. Run: pip install PyMuPDF",
            ) from exc

        file_name = os.path.basename(file_path)
        bound_log = log.bind(file_name=file_name, file_path=file_path)

        if not os.path.exists(file_path):
            raise ParserError(file_path, "File not found.")

        try:
            doc = fitz.open(file_path)
        except fitz.FileDataError as exc:
            raise ParserError(file_path, f"Corrupt or invalid PDF: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise ParserError(file_path, f"Failed to open PDF: {exc}") from exc

        try:
            # Password-protected documents report zero pages and require auth.
            if doc.needs_pass:
                raise ParserError(
                    file_path,
                    "PDF is password-protected. Remove the password before ingesting.",
                )

            pages: list[PageContent] = []
            sections: list[SectionContent] = []
            page_texts: list[str] = []

            for page_index in range(len(doc)):
                page = doc[page_index]
                page_number = page_index + 1  # 1-based

                page_text = _extract_page_text(page)
                pages.append(PageContent(page_number=page_number, text=page_text))
                page_texts.append(page_text)

                # Detect section headings from font-size heuristics
                page_sections = _extract_page_sections(
                    page=page,
                    page_text=page_text,
                    page_number=page_number,
                    char_offset=sum(len(t) + 2 for t in page_texts[:-1]),
                )
                sections.extend(page_sections)

            full_content = "\n\n".join(page_texts)

            metadata: dict[str, str] = {}
            try:
                pdf_meta = doc.metadata or {}
                if pdf_meta.get("title"):
                    metadata["title"] = pdf_meta["title"]
                if pdf_meta.get("author"):
                    metadata["author"] = pdf_meta["author"]
                if pdf_meta.get("creationDate"):
                    metadata["creation_date"] = pdf_meta["creationDate"]
            except Exception:  # noqa: BLE001
                pass  # metadata is optional; never fail the parse for it

            bound_log.info(
                "pdf_parsed",
                page_count=len(pages),
                section_count=len(sections),
                content_length=len(full_content),
            )

            return ParsedDocument(
                file_path=file_path,
                file_name=file_name,
                file_type="pdf",
                content=full_content,
                pages=pages,
                sections=sections,
                metadata=metadata,
            )

        except ParserError:
            raise  # already wrapped — pass through unchanged
        except Exception as exc:  # noqa: BLE001
            bound_log.error("pdf_parse_failed", error=str(exc), exc_info=True)
            raise ParserError(file_path, f"Unexpected error during parsing: {exc}") from exc
        finally:
            doc.close()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_page_text(page: "fitz.Page") -> str:  # type: ignore[name-defined]  # noqa: F821
    """Return cleaned text for a single PDF page.

    Uses PyMuPDF's ``get_text("text")`` which preserves reading order
    better than the default extraction mode for multi-column layouts.
    """
    try:
        text: str = page.get_text("text") or ""
        # Normalise excessive blank lines to a single blank line
        lines = text.splitlines()
        cleaned: list[str] = []
        blank_run = 0
        for line in lines:
            if line.strip() == "":
                blank_run += 1
                if blank_run <= 1:
                    cleaned.append("")
            else:
                blank_run = 0
                cleaned.append(line)
        return "\n".join(cleaned).strip()
    except Exception:  # noqa: BLE001
        return ""  # image-only / unreadable page → empty string, never fail


def _extract_page_sections(
    page: "fitz.Page",  # type: ignore[name-defined]  # noqa: F821
    page_text: str,
    page_number: int,
    char_offset: int,
) -> list[SectionContent]:
    """Detect section headings on a page using font-size heuristics.

    Algorithm
    ---------
    1. Collect all text spans with their font sizes via ``get_text("dict")``.
    2. Compute the median body font size for the page.
    3. Any span whose font size is >= ``body_size * _HEADING_FONT_RATIO``
       and whose text length is within ``[_MIN_HEADING_CHARS, _MAX_HEADING_CHARS]``
       is treated as a heading candidate.
    4. Consecutive candidates on the same line are merged.

    Returns an empty list when the page yields no headings or when the
    heuristic cannot be applied (e.g. image-only pages).
    """
    sections: list[SectionContent] = []
    try:
        import fitz  # noqa: F401 — already imported by caller
        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])

        # Collect all font sizes to compute a baseline body size
        font_sizes: list[float] = []
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = span.get("size", 0.0)
                    if size > 0:
                        font_sizes.append(size)

        if not font_sizes:
            return []

        # Median body font size
        sorted_sizes = sorted(font_sizes)
        median_size = sorted_sizes[len(sorted_sizes) // 2]
        heading_threshold = median_size * _HEADING_FONT_RATIO

        current_offset = char_offset
        for block in blocks:
            for line in block.get("lines", []):
                line_text_parts: list[str] = []
                max_size_in_line = 0.0
                for span in line.get("spans", []):
                    span_text = span.get("text", "").strip()
                    span_size = span.get("size", 0.0)
                    if span_text:
                        line_text_parts.append(span_text)
                        max_size_in_line = max(max_size_in_line, span_size)

                line_text = " ".join(line_text_parts).strip()
                if not line_text:
                    current_offset += 1  # newline character
                    continue

                if (
                    max_size_in_line >= heading_threshold
                    and _MIN_HEADING_CHARS <= len(line_text) <= _MAX_HEADING_CHARS
                ):
                    # Estimate heading level from relative font size
                    if max_size_in_line >= median_size * 1.8:
                        level = 1
                    elif max_size_in_line >= median_size * 1.5:
                        level = 2
                    elif max_size_in_line >= median_size * 1.3:
                        level = 3
                    else:
                        level = 4

                    sections.append(
                        SectionContent(
                            heading=line_text,
                            level=level,
                            text=line_text,
                            page_number=page_number,
                            char_offset=current_offset,
                        )
                    )

                current_offset += len(line_text) + 1  # +1 for newline

    except Exception:  # noqa: BLE001
        pass  # section extraction is best-effort; never fail the page parse

    return sections
