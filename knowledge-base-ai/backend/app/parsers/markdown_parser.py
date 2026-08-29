"""Markdown document parser.

Extracts text from Markdown files (.md), preserving ATX heading structure
(``# H1``, ``## H2``, etc.) as ``SectionContent`` entries.

Edge cases handled
------------------
- **Malformed / non-standard Markdown**: parsing never raises — any text that
  cannot be interpreted as a heading is treated as body content, so partial or
  synthetic Markdown always yields *something* rather than an error.
- **Empty file**: returns a ``ParsedDocument`` with empty ``content``
  (``is_empty == True``); the ingestion service decides whether to skip it.
- **YAML front-matter**: stripped before section extraction so ``---`` fences
  and metadata keys do not appear as fake headings.
- **No page concept**: Markdown has no pages.  ``pages`` always contains at
  most one synthetic entry with the full text; every ``SectionContent`` has
  ``page_number=None``.
- **Setext headings** (underlines with ``===`` / ``---``): detected in addition
  to ATX headings so documents using the older style are handled correctly.
"""
from __future__ import annotations

import os
import re

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
# Heading detection patterns
# ---------------------------------------------------------------------------

# ATX headings: ``# Heading``, ``## Heading``, up to H6.
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")

# Setext H1 ─ next line is ``===`` (one or more)
_SETEXT_H1_RE = re.compile(r"^=+\s*$")
# Setext H2 ─ next line is ``---`` (one or more, but NOT the YAML fence)
_SETEXT_H2_RE = re.compile(r"^-{2,}\s*$")

# YAML front-matter fence (must appear at the very start of the file)
_YAML_FENCE_RE = re.compile(r"^---\s*$")


def _strip_front_matter(lines: list[str]) -> list[str]:
    """Remove YAML front-matter block if present.

    Parameters
    ----------
    lines:
        All lines from the Markdown source, without a trailing newline on each.

    Returns
    -------
    list[str]
        Lines with the leading ``---`` … ``---`` block removed, or the
        original list unchanged if no front-matter was detected.
    """
    if not lines or not _YAML_FENCE_RE.match(lines[0]):
        return lines
    # Find the closing fence (starts at line 1)
    for i in range(1, len(lines)):
        if _YAML_FENCE_RE.match(lines[i]):
            return lines[i + 1 :]
    # Unclosed front-matter fence → treat the whole file as content
    return lines


def _parse_sections(lines: list[str]) -> list[SectionContent]:
    """Extract sections from a list of Markdown source lines.

    A new section begins whenever an ATX or Setext heading is encountered.
    Content before the first heading is gathered under a level-0 preamble
    section (heading = ``""``) if it contains non-blank text.

    Parameters
    ----------
    lines:
        Markdown source lines (front-matter already stripped), without
        trailing newlines.

    Returns
    -------
    list[SectionContent]
        Ordered list of sections.  May be empty for blank/whitespace-only
        files.
    """
    sections: list[SectionContent] = []

    current_heading = ""
    current_level = 0
    current_parts: list[str] = []
    current_char_offset = 0

    # Running character offset across the reconstructed full content.
    char_offset = 0

    def _flush(next_char_offset: int) -> None:
        text = "\n".join(current_parts).strip()
        if text:
            sections.append(
                SectionContent(
                    heading=current_heading,
                    level=current_level,
                    text=text,
                    page_number=None,
                    char_offset=current_char_offset,
                )
            )

    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]

        # ── ATX heading ──────────────────────────────────────────────────────
        atx_match = _ATX_HEADING_RE.match(line)
        if atx_match:
            _flush(char_offset)
            new_level = len(atx_match.group(1))
            new_heading = atx_match.group(2).strip()
            current_heading = new_heading
            current_level = new_level
            current_char_offset = char_offset
            current_parts = [line]
            char_offset += len(line) + 1
            i += 1
            continue

        # ── Setext heading ────────────────────────────────────────────────────
        # Look-ahead: current line is heading text, next is the underline.
        if i + 1 < n:
            next_line = lines[i + 1]
            if _SETEXT_H1_RE.match(next_line) and line.strip():
                _flush(char_offset)
                current_heading = line.strip()
                current_level = 1
                current_char_offset = char_offset
                current_parts = [line, next_line]
                char_offset += len(line) + 1 + len(next_line) + 1
                i += 2
                continue
            if _SETEXT_H2_RE.match(next_line) and line.strip():
                _flush(char_offset)
                current_heading = line.strip()
                current_level = 2
                current_char_offset = char_offset
                current_parts = [line, next_line]
                char_offset += len(line) + 1 + len(next_line) + 1
                i += 2
                continue

        # ── Body line ─────────────────────────────────────────────────────────
        current_parts.append(line)
        char_offset += len(line) + 1
        i += 1

    # Flush the final section.
    _flush(char_offset)
    return sections


class MarkdownParser(DocumentParser):
    """Parse Markdown files into :class:`~app.parsers.base.ParsedDocument`.

    Uses pure-Python regex-based heading extraction — no third-party Markdown
    library required.  The parser intentionally never raises on malformed
    input; at worst it returns a document with all text in a single level-0
    section.
    """

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".md", ".markdown"})

    async def parse(self, file_path: str) -> ParsedDocument:
        """Extract text and heading structure from a Markdown file.

        Parameters
        ----------
        file_path:
            Absolute path to the ``.md`` or ``.markdown`` file on disk.

        Returns
        -------
        ParsedDocument
            Populated DTO with full text content and section metadata.

        Raises
        ------
        ParserError
            If the file is not found or cannot be read (e.g., permission
            error).  Malformed Markdown never raises — it is always parsed
            best-effort.
        """
        logger = log.bind(file_path=file_path)
        logger.info("markdown_parse_start")

        if not os.path.exists(file_path):
            raise ParserError(
                file_path=file_path,
                reason="File not found",
            )

        try:
            with open(file_path, encoding="utf-8", errors="replace") as fh:
                raw = fh.read()
        except OSError as exc:
            raise ParserError(
                file_path=file_path,
                reason=f"Cannot read file: {exc}",
            ) from exc

        try:
            lines = raw.splitlines()
            lines = _strip_front_matter(lines)
            sections = _parse_sections(lines)

            full_content = "\n".join(lines).strip()

            pages: list[PageContent] = (
                [PageContent(page_number=1, text=full_content)]
                if full_content
                else []
            )

            file_name = os.path.basename(file_path)
            result = ParsedDocument(
                file_path=file_path,
                file_name=file_name,
                file_type=os.path.splitext(file_name)[1].lower(),
                content=full_content,
                pages=pages,
                sections=sections,
            )

            logger.info(
                "markdown_parse_complete",
                lines=len(lines),
                sections=len(sections),
                content_length=len(full_content),
            )
            return result

        except ParserError:
            raise
        except Exception as exc:
            logger.error(
                "markdown_parse_unexpected_error",
                error=str(exc),
                exc_info=True,
            )
            raise ParserError(
                file_path=file_path,
                reason=f"Unexpected error during Markdown parsing: {exc}",
            ) from exc
