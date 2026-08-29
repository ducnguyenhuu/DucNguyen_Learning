"""Abstract base class and shared data types for document parsers.

Every concrete parser (PDF, DOCX, Markdown) must:

1. Inherit from ``DocumentParser``.
2. Implement the single abstract method ``parse(file_path) → ParsedDocument``.
3. Handle corrupt / unreadable files by raising ``ParserError`` rather than
   letting raw exceptions propagate to callers.

Design mirrors the EmbeddingProvider / LLMProvider ABCs in
``app/providers/base.py`` — business logic never imports concrete parsers
directly; the ingestion service uses the registry in ``__init__.py``.

Usage
-----
    from app.parsers.base import DocumentParser, ParsedDocument

    class PdfParser(DocumentParser):
        @property
        def supported_extensions(self) -> frozenset[str]:
            return frozenset({".pdf"})

        async def parse(self, file_path: str) -> ParsedDocument:
            ...
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data transfer objects (DTOs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageContent:
    """Text content extracted from a single page.

    Attributes
    ----------
    page_number:
        1-based page index within the source document.
    text:
        Raw text extracted from this page.  May be empty for pages that
        contain only images or are otherwise unparseable.
    """

    page_number: int
    text: str


@dataclass(frozen=True)
class SectionContent:
    """Text content within a logical section (heading + body).

    Attributes
    ----------
    heading:
        Section heading text (e.g. "3.1 Architecture Overview").
    level:
        Heading depth — 1 for top-level (H1), 2 for H2, etc.
        0 means the content has no detected heading.
    text:
        Full text of the section, including the heading line.
    page_number:
        1-based page where this section starts, if available.
        ``None`` for formats without a page concept (e.g. plain Markdown).
    char_offset:
        Character offset of the section start within the full document
        ``content`` string.  Used by the chunker for boundary alignment.
    """

    heading: str
    level: int
    text: str
    page_number: int | None = None
    char_offset: int = 0


@dataclass
class ParsedDocument:
    """The result of parsing a single source document.

    Attributes
    ----------
    file_path:
        Absolute path to the source file, as supplied to ``parse()``.
    file_name:
        Basename of the file (e.g. ``"architecture-guide.pdf"``).
    file_type:
        Lowercase extension without the leading dot: ``"pdf"``, ``"docx"``,
        or ``"md"``.
    content:
        Full extracted text of the document, assembled from all pages /
        sections in reading order.  This is the primary input for the
        chunker.
    pages:
        Per-page breakdown.  Empty list for formats without a page concept.
        Parsers that do have pages MUST populate this list so that chunk
        metadata can reference accurate page numbers.
    sections:
        Logical section breakdown derived from headings.  Empty list if the
        document has no detectable heading structure.  The chunker uses
        section boundaries for soft-split preference (FR-002).
    metadata:
        Arbitrary key/value pairs for parser-specific extras (e.g. author,
        title, word count).  Consumers should treat all values as optional.
    """

    file_path: str
    file_name: str
    file_type: str
    content: str
    pages: list[PageContent] = field(default_factory=list)
    sections: list[SectionContent] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def page_count(self) -> int:
        """Number of pages, or 0 for page-less formats."""
        return len(self.pages)

    @property
    def is_empty(self) -> bool:
        """Return ``True`` when no text could be extracted."""
        return not self.content.strip()


# ---------------------------------------------------------------------------
# Parser error
# ---------------------------------------------------------------------------


class ParserError(Exception):
    """Raised when a parser cannot process a document.

    Attributes
    ----------
    file_path:
        Path to the document that failed to parse.
    reason:
        Human-readable explanation of the failure.
    """

    def __init__(self, file_path: str, reason: str) -> None:
        super().__init__(f"Failed to parse '{file_path}': {reason}")
        self.file_path = file_path
        self.reason = reason


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class DocumentParser(ABC):
    """Interface for extracting text and structure from a document file.

    All implementations MUST:
    - Return a valid ``ParsedDocument`` on success.
    - Raise ``ParserError`` for corrupt / unreadable input.
    - **Never** raise raw library exceptions (e.g. ``fitz.FileDataError``);
      wrap them in ``ParserError`` before propagating.
    - Be safe to call concurrently (share no mutable state between calls).

    Implementations MAY:
    - Return an empty ``content`` string for documents that yield no text
      (e.g. image-only PDFs), but MUST NOT raise ``ParserError`` in that
      case — the ingestion service decides how to handle empty documents.
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> frozenset[str]:
        """Set of lowercase file extensions this parser handles.

        Each extension must include the leading dot, e.g. ``{".pdf"}``.
        Used by the ingestion service to route files to the correct parser.
        """

    @abstractmethod
    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse the document at *file_path* and return its content.

        Parameters
        ----------
        file_path:
            Absolute path to the document to parse.

        Returns
        -------
        ParsedDocument
            Extracted text along with page and section metadata.

        Raises
        ------
        ParserError
            If the file is corrupt, unreadable, or in an unexpected format.
        """

    def supports(self, file_path: str) -> bool:
        """Return ``True`` if this parser can handle *file_path*.

        Convenience method used by the parser registry; checks the file
        extension against ``supported_extensions`` (case-insensitive).

        Parameters
        ----------
        file_path:
            Any path string — only the extension is inspected.
        """
        import os

        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.supported_extensions
