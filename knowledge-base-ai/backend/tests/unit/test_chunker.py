"""Unit tests for the text chunker (T076).

Tests cover
-----------
- Construction: valid/invalid chunk_size + chunk_overlap combinations
- ``from_settings()`` factory
- Empty document → empty list
- Single paragraph smaller than chunk_size → one chunk
- Text shorter than chunk_size → one chunk, correct offsets
- Text larger than chunk_size split at paragraph boundaries
- Overlap: consecutive chunks share the expected tail/prefix
- Grace zone: natural boundary inside (chunk_size, chunk_size × 1.5] is used
- Force-split: content with no natural boundaries beyond chunk_size
- Section boundary metadata propagated to chunks
- Page number metadata estimated from pages list
- chunk_index is sequential from 0
- start_char + end_char are accurate slices of the original content
- Whitespace-only document → empty list
- Very large single paragraph force-split into multiple chunks
"""
from __future__ import annotations

import textwrap

import pytest

from app.parsers.base import (
    PageContent,
    ParsedDocument,
    SectionContent,
)
from app.parsers.chunker import Chunker, TextChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc(
    content: str,
    sections: list[SectionContent] | None = None,
    pages: list[PageContent] | None = None,
    file_path: str = "/test/doc.md",
) -> ParsedDocument:
    return ParsedDocument(
        file_path=file_path,
        file_name="doc.md",
        file_type=".md",
        content=content,
        sections=sections or [],
        pages=pages or [],
        metadata={},
    )


def _content_of_length(n: int, char: str = "x") -> str:
    """Return a string of exactly *n* characters (no newlines)."""
    return char * n


def _paragraphs(*texts: str) -> str:
    """Join texts with double-newline (paragraph separator)."""
    return "\n\n".join(texts)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestChunkerConstruction:
    def test_valid_construction(self) -> None:
        c = Chunker(chunk_size=1000, chunk_overlap=200)
        assert c.chunk_size == 1000
        assert c.chunk_overlap == 200

    def test_overlap_equal_to_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap"):
            Chunker(chunk_size=500, chunk_overlap=500)

    def test_overlap_greater_than_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap"):
            Chunker(chunk_size=100, chunk_overlap=200)

    def test_zero_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError):
            Chunker(chunk_size=0, chunk_overlap=0)

    def test_negative_overlap_raises(self) -> None:
        with pytest.raises(ValueError):
            Chunker(chunk_size=100, chunk_overlap=-1)

    def test_zero_overlap_valid(self) -> None:
        c = Chunker(chunk_size=500, chunk_overlap=0)
        assert c.chunk_overlap == 0

    def test_from_settings(self) -> None:
        class FakeSettings:
            chunk_size = 800
            chunk_overlap = 150

        c = Chunker.from_settings(FakeSettings())
        assert c.chunk_size == 800
        assert c.chunk_overlap == 150


# ---------------------------------------------------------------------------
# Empty / trivial inputs
# ---------------------------------------------------------------------------


class TestChunkerEmptyInputs:
    def setup_method(self) -> None:
        self.chunker = Chunker(chunk_size=100, chunk_overlap=20)

    def test_empty_content_returns_empty_list(self) -> None:
        doc = _doc("")
        assert self.chunker.chunk(doc) == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        doc = _doc("   \n\n\t  \n")
        assert self.chunker.chunk(doc) == []

    def test_single_word_returns_one_chunk(self) -> None:
        doc = _doc("hello")
        chunks = self.chunker.chunk(doc)
        assert len(chunks) == 1
        assert chunks[0].text == "hello"


# ---------------------------------------------------------------------------
# Basic chunking behaviour
# ---------------------------------------------------------------------------


class TestChunkerBasic:
    def setup_method(self) -> None:
        self.chunker = Chunker(chunk_size=50, chunk_overlap=10)

    def test_short_content_single_chunk(self) -> None:
        content = "Short document that fits in one chunk."
        doc = _doc(content)
        chunks = self.chunker.chunk(doc)
        assert len(chunks) == 1
        assert chunks[0].text == content.strip()

    def test_single_chunk_start_and_end_offsets(self) -> None:
        content = "Hello world"
        doc = _doc(content)
        chunks = self.chunker.chunk(doc)
        assert chunks[0].start_char == 0
        assert chunks[0].end_char == len(content)

    def test_chunk_index_starts_at_zero(self) -> None:
        content = _content_of_length(200)
        doc = _doc(content)
        chunks = self.chunker.chunk(doc)
        assert chunks[0].chunk_index == 0

    def test_chunk_indices_are_sequential(self) -> None:
        content = _content_of_length(200)
        doc = _doc(content)
        chunks = self.chunker.chunk(doc)
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_chunk_text_matches_content_slice(self) -> None:
        """chunk.text must equal content[start_char:end_char].strip()."""
        content = _paragraphs(
            "First paragraph here with some words.",
            "Second paragraph here with more words.",
            "Third paragraph with even more text here.",
        )
        chunker = Chunker(chunk_size=50, chunk_overlap=10)
        doc = _doc(content)
        for chunk in chunker.chunk(doc):
            raw_slice = content[chunk.start_char : chunk.end_char]
            assert chunk.text == raw_slice.strip()

    def test_all_content_covered(self) -> None:
        """The union of all chunk ranges must cover [0, len(content))."""
        content = _paragraphs(
            "Alpha " * 10,
            "Beta " * 10,
            "Gamma " * 10,
        )
        chunker = Chunker(chunk_size=60, chunk_overlap=15)
        doc = _doc(content)
        chunks = chunker.chunk(doc)
        assert len(chunks) >= 1
        # First chunk starts at 0 (or past leading whitespace).
        assert chunks[0].start_char == 0
        # Last chunk's end_char must reach or cover the last non-whitespace.
        last_non_ws = len(content.rstrip())
        assert chunks[-1].end_char >= last_non_ws

    def test_file_path_and_name_propagated(self) -> None:
        doc = _doc("Some content here.", file_path="/data/test.md")
        doc.file_name = "test.md"
        chunks = Chunker(chunk_size=100, chunk_overlap=10).chunk(doc)
        assert chunks[0].file_path == "/data/test.md"
        assert chunks[0].file_name == "test.md"


# ---------------------------------------------------------------------------
# Overlap
# ---------------------------------------------------------------------------


class TestChunkerOverlap:
    def test_overlap_text_shared_between_consecutive_chunks(self) -> None:
        """Last `chunk_overlap` chars of chunk N must appear at start of N+1."""
        # Use a simple repeating content with no natural boundaries so splits
        # land exactly at chunk_size boundaries, making overlap predictable.
        chunk_size = 50
        overlap = 10
        content = _content_of_length(200, char="a")
        chunker = Chunker(chunk_size=chunk_size, chunk_overlap=overlap)
        doc = _doc(content)
        chunks = chunker.chunk(doc)

        assert len(chunks) >= 2
        for i in range(len(chunks) - 1):
            tail = chunks[i].text[-overlap:]
            head = chunks[i + 1].text[:overlap]
            assert tail == head, (
                f"Chunk {i} tail {tail!r} != chunk {i+1} head {head!r}"
            )

    def test_zero_overlap_produces_no_shared_text(self) -> None:
        content = _content_of_length(200, char="b")
        chunker = Chunker(chunk_size=50, chunk_overlap=0)
        doc = _doc(content)
        chunks = chunker.chunk(doc)
        assert len(chunks) >= 2
        # With zero overlap, end of chunk N equals start of chunk N+1.
        for i in range(len(chunks) - 1):
            assert chunks[i].end_char == chunks[i + 1].start_char


# ---------------------------------------------------------------------------
# Paragraph boundary preservation
# ---------------------------------------------------------------------------


class TestChunkerBoundaryPreservation:
    def test_splits_at_paragraph_boundary_within_chunk_size(self) -> None:
        """When a paragraph boundary falls within chunk_size, it is used."""
        chunker = Chunker(chunk_size=100, chunk_overlap=10)
        # Two short paragraphs, each < 100 chars, combined > 100 chars.
        para1 = "A" * 60
        para2 = "B" * 60
        content = _paragraphs(para1, para2)
        doc = _doc(content)
        chunks = chunker.chunk(doc)
        # The first chunk should contain para1 but not all of para2.
        assert "A" in chunks[0].text
        # Some chunk must start with "B" content.
        assert any("B" in c.text for c in chunks)

    def test_grace_zone_boundary_used_before_force_split(self) -> None:
        """Boundary inside (chunk_size, chunk_size × 1.5] is preferred over force-split."""
        chunker = Chunker(chunk_size=100, chunk_overlap=10)
        # para1 = 90 chars, para2 = 30 chars → combined = 120 chars.
        # 120 <= 150 (1.5 × 100), so the paragraph boundary should be used.
        para1 = "C" * 90
        para2 = "D" * 30
        content = _paragraphs(para1, para2)
        doc = _doc(content)
        chunks = chunker.chunk(doc)
        # First chunk must end at the paragraph boundary (no "D" chars).
        assert "D" not in chunks[0].text
        # Second chunk must start with "D" chars.
        assert "D" in chunks[1].text if len(chunks) > 1 else True

    def test_section_boundary_used_as_soft_split(self) -> None:
        """section.char_offset is treated as a soft split point."""
        chunker = Chunker(chunk_size=100, chunk_overlap=0)
        # Build content: 80-char header section + 80-char body section.
        sec1_text = "Section one body text. " * 4   # ~92 chars
        sec2_text = "Section two body text. " * 4   # ~92 chars
        content = sec1_text + sec2_text
        sections = [
            SectionContent(
                heading="Section One", level=1, text=sec1_text,
                page_number=1, char_offset=0,
            ),
            SectionContent(
                heading="Section Two", level=1, text=sec2_text,
                page_number=2, char_offset=len(sec1_text),
            ),
        ]
        doc = _doc(content, sections=sections)
        chunks = chunker.chunk(doc)
        # The second chunk should start at the section boundary.
        assert any(c.start_char == len(sec1_text) for c in chunks)


# ---------------------------------------------------------------------------
# Force-split (no natural boundaries)
# ---------------------------------------------------------------------------


class TestChunkerForceSplit:
    def test_long_paragraph_force_split(self) -> None:
        """A single paragraph > chunk_size × 1.5 must be split."""
        chunker = Chunker(chunk_size=50, chunk_overlap=10)
        content = _content_of_length(500, char="x")  # No newlines anywhere.
        doc = _doc(content)
        chunks = chunker.chunk(doc)
        assert len(chunks) > 1
        for c in chunks:
            # No chunk may be more than chunk_size + chunk_overlap wide.
            assert len(c.text) <= chunker.chunk_size + chunker.chunk_overlap

    def test_force_split_chunks_cover_full_content(self) -> None:
        chunker = Chunker(chunk_size=50, chunk_overlap=0)
        content = _content_of_length(250, char="y")
        doc = _doc(content)
        chunks = chunker.chunk(doc)
        # Reconstruct: each chunk[i].start_char to chunk[i].end_char
        # should span entire content without gaps.
        reconstructed = set()
        for c in chunks:
            reconstructed.update(range(c.start_char, c.end_char))
        assert all(i in reconstructed for i in range(len(content)))


# ---------------------------------------------------------------------------
# Metadata propagation
# ---------------------------------------------------------------------------


class TestChunkerMetadata:
    def test_no_sections_no_page_number_defaults(self) -> None:
        chunker = Chunker(chunk_size=50, chunk_overlap=5)
        doc = _doc("Some content here that spans multiple chunker boundaries yes.")
        chunks = chunker.chunk(doc)
        for c in chunks:
            assert c.section_heading == ""
            assert c.section_level == 0
            assert c.page_number is None

    def test_section_heading_assigned_to_chunks(self) -> None:
        chunker = Chunker(chunk_size=200, chunk_overlap=10)
        body = "Word " * 30  # 150 chars
        sections = [
            SectionContent(
                heading="Introduction", level=1, text=body,
                page_number=1, char_offset=0,
            ),
        ]
        doc = _doc(body, sections=sections)
        chunks = chunker.chunk(doc)
        assert chunks[0].section_heading == "Introduction"
        assert chunks[0].section_level == 1

    def test_section_page_number_propagated(self) -> None:
        chunker = Chunker(chunk_size=200, chunk_overlap=10)
        body = "Word " * 30
        sections = [
            SectionContent(
                heading="Chapter 1", level=1, text=body,
                page_number=5, char_offset=0,
            ),
        ]
        doc = _doc(body, sections=sections)
        chunks = chunker.chunk(doc)
        assert chunks[0].page_number == 5

    def test_chunk_picks_nearest_preceding_section(self) -> None:
        """A chunk starting partway into section 2 should report section 2."""
        chunker = Chunker(chunk_size=50, chunk_overlap=0)
        sec1 = "A" * 60
        sec2 = "B" * 60
        content = sec1 + sec2
        sections = [
            SectionContent(
                heading="Alpha", level=1, text=sec1,
                page_number=1, char_offset=0,
            ),
            SectionContent(
                heading="Beta", level=2, text=sec2,
                page_number=2, char_offset=len(sec1),
            ),
        ]
        doc = _doc(content, sections=sections)
        chunks = chunker.chunk(doc)
        # Find a chunk that starts inside sec2
        sec2_chunks = [c for c in chunks if c.start_char >= len(sec1)]
        assert sec2_chunks, "Expected at least one chunk in the second section"
        for c in sec2_chunks:
            assert c.section_heading == "Beta"
            assert c.section_level == 2

    def test_page_number_estimated_from_pages_list(self) -> None:
        """When sections have no page info, estimate from pages list."""
        chunker = Chunker(chunk_size=200, chunk_overlap=10)
        page1_text = "First page content. " * 5   # ~100 chars
        page2_text = "Second page content. " * 5  # ~100 chars
        content = page1_text + page2_text
        pages = [
            PageContent(page_number=1, text=page1_text),
            PageContent(page_number=2, text=page2_text),
        ]
        doc = _doc(content, pages=pages)
        chunks = chunker.chunk(doc)
        # First chunk should be on page 1.
        assert chunks[0].page_number == 1


# ---------------------------------------------------------------------------
# Larger integration-style scenario
# ---------------------------------------------------------------------------


class TestChunkerIntegration:
    def test_multi_section_document(self) -> None:
        """Realistic document with sections, pages, and varying paragraph sizes."""
        chunker = Chunker(chunk_size=200, chunk_overlap=40)

        intro = "Introduction paragraph. " * 4          # ~96 chars
        background = "Background detail. " * 6          # ~114 chars
        methods = "Methodology steps described here. " * 5  # ~170 chars
        results = "Results show improvement. " * 6      # ~150 chars

        content = _paragraphs(intro, background, methods, results)

        sections = [
            SectionContent(
                heading="Introduction", level=1, text=intro,
                page_number=1, char_offset=0,
            ),
            SectionContent(
                heading="Background", level=2, text=background,
                page_number=1, char_offset=len(intro) + 2,
            ),
            SectionContent(
                heading="Methods", level=1, text=methods,
                page_number=2,
                char_offset=len(intro) + 2 + len(background) + 2,
            ),
            SectionContent(
                heading="Results", level=1, text=results,
                page_number=3,
                char_offset=len(intro) + 2 + len(background) + 2 + len(methods) + 2,
            ),
        ]

        doc = _doc(content, sections=sections)
        chunks = chunker.chunk(doc)

        assert len(chunks) >= 2

        # All chunk indices are sequential.
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

        # All chunks have a section heading (content starts at offset 0 which
        # aligns with the first section).
        assert all(c.section_heading != "" for c in chunks)

        # No chunk text is empty.
        assert all(c.text.strip() for c in chunks)

        # No chunk is longer than chunk_size × 1.5 + overlap.
        for c in chunks:
            assert len(c.text) <= chunker.chunk_size * 1.5 + chunker.chunk_overlap
