"""Text chunker — splits a ParsedDocument into overlapping text chunks.

Strategy
--------
Chunks are produced by walking the full ``content`` string and using
**soft split points** (section and paragraph boundaries) to find natural
break positions.  The algorithm is:

1. Collect all preferred split offsets:
   - Section boundaries from ``ParsedDocument.sections[].char_offset``
   - Paragraph boundaries (double newline ``\\n\\n``) within ``content``

2. Walk forward through the content.  At each position:
   - Extend the current chunk up to ``CHUNK_SIZE`` characters.
   - Look for the last soft split point that falls within the *grace zone*
     ``[CHUNK_SIZE, CHUNK_SIZE × 1.5]``.  If one exists, extend to it
     (FR-002 boundary preservation).
   - If no soft split point is found before ``CHUNK_SIZE × 1.5``,
     force-split exactly at ``CHUNK_SIZE`` (hard limit — avoids indefinitely
     large chunks from long paragraphs).

3. After emitting a chunk, back up by ``CHUNK_OVERLAP`` characters so that
   the next chunk shares a tail with the previous one (continuity for
   embedding/retrieval).

4. Each :class:`TextChunk` carries position metadata:
   - ``start_char`` / ``end_char`` — character offsets within ``content``
   - ``chunk_index`` — 0-based sequence number within the document
   - ``section_heading`` / ``section_level`` — from the enclosing section
   - ``page_number`` — best estimate from section metadata or page list

Edge cases
----------
- **Empty document**: returns ``[]``.
- **Single-paragraph document smaller than CHUNK_SIZE**: returns one chunk.
- **Single paragraph larger than CHUNK_SIZE × 1.5**: force-split every
  ``CHUNK_SIZE`` characters.
- **chunk_overlap ≥ chunk_size**: raises ``ValueError`` at construction time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from app.parsers.base import PageContent, ParsedDocument, SectionContent

log = structlog.get_logger(__name__)

# Multiplier applied to ``chunk_size`` to compute the grace-zone ceiling.
_FORCE_SPLIT_THRESHOLD: float = 1.5

# Regex for one or more blank lines (paragraph boundary).
_BLANK_LINE_RE = re.compile(r"\n{2,}")


# ---------------------------------------------------------------------------
# Data transfer object
# ---------------------------------------------------------------------------


@dataclass
class TextChunk:
    """A fixed-size text chunk produced by the chunker.

    Attributes
    ----------
    text:
        The chunk text, possibly sharing an overlap suffix with the
        previous chunk and an overlap prefix with the next chunk.
    chunk_index:
        0-based sequential index within the source document.
    file_path:
        Absolute path of the source document (for downstream metadata).
    file_name:
        Basename of the source document.
    start_char:
        Character offset of ``text[0]`` within ``ParsedDocument.content``.
    end_char:
        Character offset one past ``text[-1]`` within
        ``ParsedDocument.content`` (exclusive).
    page_number:
        Best estimated 1-based page number where this chunk starts, or
        ``None`` when the source format has no page concept.
    section_heading:
        Heading of the section this chunk belongs to, or ``""`` when the
        document has no heading structure.
    section_level:
        Depth of the enclosing section (1 = H1, 2 = H2, …). 0 means no
        heading.
    """

    text: str
    chunk_index: int
    file_path: str
    file_name: str
    start_char: int
    end_char: int
    page_number: int | None
    section_heading: str
    section_level: int


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------


class Chunker:
    """Splits a :class:`~app.parsers.base.ParsedDocument` into chunks.

    Parameters
    ----------
    chunk_size:
        Target maximum character count per chunk (default 1 000 chars).
    chunk_overlap:
        Number of characters shared between consecutive chunks for context
        continuity (default 200 chars).  Must be strictly less than
        ``chunk_size``.

    Raises
    ------
    ValueError
        If ``chunk_overlap >= chunk_size``.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be less than "
                f"chunk_size ({chunk_size})"
            )
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap cannot be negative, got {chunk_overlap}")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._grace_limit = int(chunk_size * _FORCE_SPLIT_THRESHOLD)

    @classmethod
    def from_settings(cls, settings: object) -> "Chunker":
        """Instantiate from a :class:`~app.config.Settings` object.

        Parameters
        ----------
        settings:
            Any object with integer attributes ``chunk_size`` and
            ``chunk_overlap`` (matches :class:`app.config.Settings`).
        """
        return cls(
            chunk_size=int(getattr(settings, "chunk_size", 1000)),
            chunk_overlap=int(getattr(settings, "chunk_overlap", 200)),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, document: ParsedDocument) -> list[TextChunk]:
        """Split *document* into overlapping :class:`TextChunk` objects.

        Parameters
        ----------
        document:
            A fully parsed document.  Only ``content``, ``sections``, and
            ``pages`` are used; the other fields are copied to each chunk
            for reference.

        Returns
        -------
        list[TextChunk]
            Ordered list of chunks.  Empty when ``document.is_empty``.
        """
        content = document.content
        if not content.strip():
            log.debug("chunker_skip_empty", file_path=document.file_path)
            return []

        soft_splits = self._compute_soft_splits(content, document.sections)
        chunks: list[TextChunk] = []
        chunk_start = 0
        content_len = len(content)

        while chunk_start < content_len:
            chunk_end = self._find_chunk_end(
                content, chunk_start, content_len, soft_splits
            )

            raw_text = content[chunk_start:chunk_end]
            text = raw_text.strip()

            if text:
                heading, level, page_number = self._resolve_metadata(
                    chunk_start,
                    document.sections,
                    document.pages,
                    content,
                )
                chunks.append(
                    TextChunk(
                        text=text,
                        chunk_index=len(chunks),
                        file_path=document.file_path,
                        file_name=document.file_name,
                        start_char=chunk_start,
                        end_char=chunk_end,
                        page_number=page_number,
                        section_heading=heading,
                        section_level=level,
                    )
                )

            # When the chunk consumed everything up to the end, we are done.
            # Without this guard the overlap calculation would send cursor
            # backwards, reprocessing already-consumed characters forever.
            if chunk_end >= content_len:
                break

            # Advance, backing up by overlap so consecutive chunks share text.
            next_start = chunk_end - self.chunk_overlap
            if next_start <= chunk_start:
                # Safety valve: always move forward at least 1 character to
                # prevent an infinite loop when overlap ≈ chunk_size.
                next_start = chunk_start + 1
            chunk_start = next_start

        log.info(
            "chunker_complete",
            file_path=document.file_path,
            chunk_count=len(chunks),
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        return chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_soft_splits(
        self, content: str, sections: list[SectionContent]
    ) -> list[int]:
        """Return a sorted list of character offsets where splitting is preferred.

        Combines section boundaries (from ``sections[].char_offset``) and
        paragraph boundaries (double newlines) discovered in *content*.
        """
        offsets: set[int] = set()
        content_len = len(content)

        # Section boundaries declared by the parser.
        for sec in sections:
            if 0 < sec.char_offset < content_len:
                offsets.add(sec.char_offset)

        # Paragraph boundaries (two or more consecutive newlines).
        for match in _BLANK_LINE_RE.finditer(content):
            split_at = match.end()
            if 0 < split_at < content_len:
                offsets.add(split_at)

        return sorted(offsets)

    def _find_chunk_end(
        self,
        content: str,
        start: int,
        content_len: int,
        soft_splits: list[int],
    ) -> int:
        """Determine where the current chunk should end.

        Parameters
        ----------
        content:
            Full document content string.
        start:
            Current chunk start offset.
        content_len:
            Length of *content*.
        soft_splits:
            Sorted preferred split offsets.

        Returns
        -------
        int
            Exclusive end offset for this chunk.
        """
        ideal_end = start + self.chunk_size
        grace_end = start + self._grace_limit

        # All content fits in one final chunk.
        if ideal_end >= content_len:
            return content_len

        # Search for the best soft split point within (start, grace_end].
        # Strategy: take the last soft split that is:
        #   1. After `start` (cannot split at the start)
        #   2. At or before `grace_end`
        # Among candidates, prefer splits in [ideal_end, grace_end] (they
        # honour boundary preference while still ending near the target size).
        # Fall back to splits before ideal_end if nothing else exists.
        best_before_ideal: int | None = None
        best_in_grace: int | None = None

        for sp in soft_splits:
            if sp <= start:
                continue
            if sp > grace_end:
                break
            if sp <= ideal_end:
                best_before_ideal = sp
            else:
                # sp is in (ideal_end, grace_end] — this is the grace zone.
                # Use the first one we find in the grace zone (preserve as
                # much of the natural boundary as reasonably possible).
                if best_in_grace is None:
                    best_in_grace = sp

        if best_in_grace is not None:
            # A boundary inside the grace zone — split there.
            return best_in_grace

        if best_before_ideal is not None:
            # A boundary within [start, ideal_end] — use the last one.
            return best_before_ideal

        # No soft split found — force-split at the hard limit.
        return min(ideal_end, content_len)

    def _resolve_metadata(
        self,
        start_char: int,
        sections: list[SectionContent],
        pages: list[PageContent],
        content: str,
    ) -> tuple[str, int, int | None]:
        """Return ``(section_heading, section_level, page_number)`` for *start_char*.

        The enclosing section is the last section whose ``char_offset`` is ≤
        *start_char*.  Page number is resolved similarly from section metadata
        first, then from the pages list by cumulative text length.
        """
        heading = ""
        level = 0
        page_number: int | None = None

        # Walk sections in order — each replaces the previous when its
        # char_offset is still ≤ start_char.
        for sec in sections:
            if sec.char_offset <= start_char:
                heading = sec.heading
                level = sec.level
                if sec.page_number is not None:
                    page_number = sec.page_number
            else:
                break

        # If sections provide no page info, estimate from the pages list
        # by cumulative character offsets.
        if page_number is None and pages:
            page_number = self._page_number_from_pages(
                start_char, pages, content
            )

        return heading, level, page_number

    @staticmethod
    def _page_number_from_pages(
        start_char: int,
        pages: list[PageContent],
        content: str,
    ) -> int | None:
        """Estimate the page number for *start_char* using the pages list.

        This is approximate: it assumes the parser assembled ``content`` by
        concatenating page texts in order (possibly with separating whitespace).
        We search for each page's text within ``content`` starting from the
        cumulative offset to handle any separators.
        """
        cursor = 0
        for page in pages:
            page_text = page.text
            if not page_text:
                continue
            # Search for the page text starting at cursor.
            idx = content.find(page_text, cursor)
            if idx == -1:
                # Fallback: advance by text length (tolerates minor differences).
                cursor += len(page_text)
            else:
                page_start = idx
                page_end = idx + len(page_text)
                if page_start <= start_char < page_end:
                    return page.page_number
                cursor = page_end

        # Could not map — return the last page's number as a fallback.
        return pages[-1].page_number if pages else None
