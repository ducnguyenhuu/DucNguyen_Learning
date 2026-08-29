"""Unit tests for all document parsers.

Tests cover
-----------
- Happy-path parsing: text extraction, section structure, page counts
- Error handling: file-not-found, corrupt files, unsupported formats
- Edge cases: empty documents, malformed content, unusual encodings
- ``supports()`` helper for each parser

Structure
---------
Tests are grouped by parser class, each section in a dedicated ``TestXxxParser``
class.  All ``parse()`` calls are ``async`` — pytest-asyncio (``asyncio_mode =
auto``) handles the event loop automatically via ``pytest.ini``.
"""
from __future__ import annotations

import os
import textwrap

import pytest

from app.parsers.base import (
    DocumentParser,
    PageContent,
    ParsedDocument,
    ParserError,
    SectionContent,
)
from app.parsers.docx_parser import DocxParser, _parse_heading_level
from app.parsers.excel_parser import ExcelParser
from app.parsers.markdown_parser import MarkdownParser
from app.parsers.pdf_parser import PdfParser


# ===========================================================================
# Base / shared helpers
# ===========================================================================


class TestParserError:
    """Tests for the ParserError exception class."""

    def test_attributes_stored(self) -> None:
        err = ParserError("/some/file.pdf", "file is corrupted")
        assert err.file_path == "/some/file.pdf"
        assert err.reason == "file is corrupted"

    def test_is_exception_subclass(self) -> None:
        assert issubclass(ParserError, Exception)

    def test_str_contains_reason(self) -> None:
        err = ParserError("/some/file.pdf", "needs password")
        assert "needs password" in str(err)


class TestParsedDocument:
    """Tests for ParsedDocument properties."""

    def _make_doc(self, content: str = "", pages: list[PageContent] | None = None) -> ParsedDocument:
        return ParsedDocument(
            file_path="/test/doc.txt",
            file_name="doc.txt",
            file_type=".txt",
            content=content,
            pages=pages or [],
            sections=[],
            metadata={},
        )

    def test_is_empty_true_when_no_content(self) -> None:
        doc = self._make_doc(content="")
        assert doc.is_empty is True

    def test_is_empty_false_when_has_content(self) -> None:
        doc = self._make_doc(content="hello")
        assert doc.is_empty is False

    def test_page_count_zero(self) -> None:
        doc = self._make_doc()
        assert doc.page_count == 0

    def test_page_count_reflects_pages_list(self) -> None:
        pages = [PageContent(page_number=1, text="p1"), PageContent(page_number=2, text="p2")]
        doc = self._make_doc(content="p1 p2", pages=pages)
        assert doc.page_count == 2


# ===========================================================================
# DOCX parser helpers
# ===========================================================================


class TestParseHeadingLevel:
    """Unit tests for the internal ``_parse_heading_level`` helper."""

    @pytest.mark.parametrize(
        "style_name,expected",
        [
            ("Heading 1", 1),
            ("Heading 2", 2),
            ("Heading 6", 6),
            ("heading 3", 3),   # case-insensitive
            ("HEADING 4", 4),
            ("Normal", 0),
            ("List Bullet", 0),
            ("Heading", 0),     # no number
            ("Heading 7", 0),   # above max
            ("Heading 0", 0),   # below min
            ("HeadingX", 0),    # non-numeric suffix
        ],
    )
    def test_parse_heading_level(self, style_name: str, expected: int) -> None:
        assert _parse_heading_level(style_name) == expected


# ===========================================================================
# MarkdownParser
# ===========================================================================


class TestMarkdownParser:
    """Tests for :class:`app.parsers.markdown_parser.MarkdownParser`."""

    def setup_method(self) -> None:
        self.parser = MarkdownParser()

    # ── supports() ──────────────────────────────────────────────────────────

    def test_supports_md_extension(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "readme.md"
        p.touch()
        assert self.parser.supports(str(p)) is True

    def test_supports_markdown_extension(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "doc.markdown"
        p.touch()
        assert self.parser.supports(str(p)) is True

    def test_does_not_support_txt(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "readme.txt"
        p.touch()
        assert self.parser.supports(str(p)) is False

    def test_does_not_support_pdf(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "doc.pdf"
        p.touch()
        assert self.parser.supports(str(p)) is False

    # ── File-not-found ───────────────────────────────────────────────────────

    async def test_file_not_found_raises_parser_error(self, nonexistent_file: str) -> None:
        # Give it a .md extension so FileNotFound path is exercised.
        md_path = nonexistent_file.replace(".pdf", ".md")
        with pytest.raises(ParserError) as exc_info:
            await self.parser.parse(md_path)
        assert exc_info.value.file_path == md_path

    # ── Empty file ───────────────────────────────────────────────────────────

    async def test_empty_file_returns_empty_document(self, md_empty: str) -> None:
        doc = await self.parser.parse(md_empty)
        assert isinstance(doc, ParsedDocument)
        assert doc.is_empty is True
        assert doc.sections == []

    # ── ATX headings ────────────────────────────────────────────────────────

    async def test_atx_headings_detected(self, md_simple: str) -> None:
        doc = await self.parser.parse(md_simple)
        headings = {s.heading: s.level for s in doc.sections}
        assert "Introduction" in headings
        assert headings["Introduction"] == 1
        assert "Background" in headings
        assert headings["Background"] == 2
        assert "Detail" in headings
        assert headings["Detail"] == 3

    async def test_atx_heading_content_preserved(self, md_simple: str) -> None:
        doc = await self.parser.parse(md_simple)
        intro_section = next(s for s in doc.sections if s.heading == "Introduction")
        assert "introduction paragraph" in intro_section.text.lower()

    async def test_file_type_set_from_md_extension(self, md_simple: str) -> None:
        doc = await self.parser.parse(md_simple)
        assert doc.file_type == ".md"

    # ── .markdown extension ──────────────────────────────────────────────────

    async def test_markdown_extension_parsed(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "doc.markdown"
        p.write_text("# Hello\n\nSome text.\n", encoding="utf-8")
        doc = await self.parser.parse(str(p))
        assert doc.file_type == ".markdown"
        assert any(s.heading == "Hello" for s in doc.sections)

    # ── Setext headings ──────────────────────────────────────────────────────

    async def test_setext_h1_detected(self, md_setext: str) -> None:
        doc = await self.parser.parse(md_setext)
        levels = {s.heading: s.level for s in doc.sections}
        assert "Main Title" in levels
        assert levels["Main Title"] == 1

    async def test_setext_h2_detected(self, md_setext: str) -> None:
        doc = await self.parser.parse(md_setext)
        levels = {s.heading: s.level for s in doc.sections}
        assert "Section Two" in levels
        assert levels["Section Two"] == 2

    # ── YAML front-matter ────────────────────────────────────────────────────

    async def test_front_matter_stripped(self, md_front_matter: str) -> None:
        doc = await self.parser.parse(md_front_matter)
        # YAML keys must not appear as section headings or content.
        all_headings = {s.heading for s in doc.sections}
        assert "title" not in all_headings
        assert "author" not in all_headings
        assert "date" not in all_headings

    async def test_content_after_front_matter_present(self, md_front_matter: str) -> None:
        doc = await self.parser.parse(md_front_matter)
        assert "Real Content" in {s.heading for s in doc.sections}

    # ── No headings ──────────────────────────────────────────────────────────

    async def test_no_headings_file_not_empty(self, md_no_headings: str) -> None:
        doc = await self.parser.parse(md_no_headings)
        assert not doc.is_empty
        # Content should be present even with no headings.
        assert "plain text" in doc.content.lower()

    # ── Malformed input ──────────────────────────────────────────────────────

    async def test_malformed_markdown_no_exception(self, md_malformed: str) -> None:
        """Parser must never raise on malformed Markdown."""
        doc = await self.parser.parse(md_malformed)
        assert isinstance(doc, ParsedDocument)

    # ── Full content field ───────────────────────────────────────────────────

    async def test_full_content_populated(self, md_simple: str) -> None:
        doc = await self.parser.parse(md_simple)
        assert len(doc.content) > 0
        assert "Introduction" in doc.content


# ===========================================================================
# DocxParser
# ===========================================================================


class TestDocxParser:
    """Tests for :class:`app.parsers.docx_parser.DocxParser`."""

    def setup_method(self) -> None:
        self.parser = DocxParser()

    # ── supports() ──────────────────────────────────────────────────────────

    def test_supports_docx_extension(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "report.docx"
        p.touch()
        assert self.parser.supports(str(p)) is True

    def test_does_not_support_doc(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "legacy.doc"
        p.touch()
        assert self.parser.supports(str(p)) is False

    def test_does_not_support_pdf(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "doc.pdf"
        p.touch()
        assert self.parser.supports(str(p)) is False

    # ── File-not-found ───────────────────────────────────────────────────────

    async def test_file_not_found_raises_parser_error(self, tmp_path: "os.PathLike[str]") -> None:
        missing = str(tmp_path / "missing.docx")
        with pytest.raises(ParserError) as exc_info:
            await self.parser.parse(missing)
        assert exc_info.value.file_path == missing

    # ── Corrupt file ─────────────────────────────────────────────────────────

    async def test_corrupt_file_raises_parser_error(self, docx_corrupt: str) -> None:
        with pytest.raises(ParserError) as exc_info:
            await self.parser.parse(docx_corrupt)
        assert exc_info.value.file_path == docx_corrupt

    # ── Empty document ───────────────────────────────────────────────────────

    async def test_empty_docx_is_empty(self, docx_empty: str) -> None:
        doc = await self.parser.parse(docx_empty)
        assert isinstance(doc, ParsedDocument)
        assert doc.is_empty is True

    # ── Document with headings ───────────────────────────────────────────────

    async def test_headings_produce_sections(self, docx_with_headings: str) -> None:
        doc = await self.parser.parse(docx_with_headings)
        headings = {s.heading: s.level for s in doc.sections}
        assert "Introduction" in headings
        assert headings["Introduction"] == 1
        assert "Background" in headings
        assert headings["Background"] == 2
        assert "Conclusion" in headings
        assert headings["Conclusion"] == 1

    async def test_section_text_captured(self, docx_with_headings: str) -> None:
        doc = await self.parser.parse(docx_with_headings)
        intro = next(s for s in doc.sections if s.heading == "Introduction")
        assert "introduction paragraph" in intro.text.lower()

    async def test_full_content_populated(self, docx_with_headings: str) -> None:
        doc = await self.parser.parse(docx_with_headings)
        assert len(doc.content) > 0

    async def test_file_name_and_type(self, docx_with_headings: str) -> None:
        doc = await self.parser.parse(docx_with_headings)
        assert doc.file_type == ".docx"
        assert doc.file_name.endswith(".docx")

    # ── Synthetic single page ─────────────────────────────────────────────────

    async def test_page_count_is_one(self, docx_with_headings: str) -> None:
        """DOCX always yields exactly one synthetic PageContent."""
        doc = await self.parser.parse(docx_with_headings)
        assert doc.page_count == 1

    async def test_section_page_number_is_none(self, docx_with_headings: str) -> None:
        """DOCX sections always have page_number=None."""
        doc = await self.parser.parse(docx_with_headings)
        for section in doc.sections:
            assert section.page_number is None

    # ── Document with only body text ─────────────────────────────────────────

    async def test_no_headings_body_text_captured(self, docx_no_headings: str) -> None:
        doc = await self.parser.parse(docx_no_headings)
        assert not doc.is_empty
        assert "First paragraph" in doc.content


# ===========================================================================
# ExcelParser
# ===========================================================================


class TestExcelParser:
    """Tests for :class:`app.parsers.excel_parser.ExcelParser`."""

    def setup_method(self) -> None:
        self.parser = ExcelParser()

    # ── supported_extensions ────────────────────────────────────────────────

    def test_supported_extensions_contains_only_xlsx(self) -> None:
        assert self.parser.supported_extensions == frozenset({".xlsx"})

    # ── supports() ──────────────────────────────────────────────────────────

    def test_supports_xlsx_extension(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "data.xlsx"
        p.touch()
        assert self.parser.supports(str(p)) is True

    def test_does_not_support_xls(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "data.xls"
        p.touch()
        assert self.parser.supports(str(p)) is False

    def test_does_not_support_csv(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "data.csv"
        p.touch()
        assert self.parser.supports(str(p)) is False

    # ── .xls rejection ──────────────────────────────────────────────────────

    async def test_xls_raises_parser_error_with_convert_message(self, xls_file: str) -> None:
        with pytest.raises(ParserError) as exc_info:
            await self.parser.parse(xls_file)
        error = exc_info.value
        assert error.file_path == xls_file
        assert "convert" in error.reason.lower()

    # ── File-not-found ───────────────────────────────────────────────────────

    async def test_file_not_found_raises_parser_error(self, tmp_path: "os.PathLike[str]") -> None:
        missing = str(tmp_path / "missing.xlsx")
        with pytest.raises(ParserError) as exc_info:
            await self.parser.parse(missing)
        assert exc_info.value.file_path == missing

    # ── Corrupt file ─────────────────────────────────────────────────────────

    async def test_corrupt_file_raises_parser_error(self, xlsx_corrupt: str) -> None:
        with pytest.raises(ParserError) as exc_info:
            await self.parser.parse(xlsx_corrupt)
        assert exc_info.value.file_path == xlsx_corrupt

    # ── Multi-sheet workbook ─────────────────────────────────────────────────

    async def test_multi_sheet_one_section_per_sheet(self, xlsx_multi_sheet: str) -> None:
        pytest.importorskip("openpyxl")
        doc = await self.parser.parse(xlsx_multi_sheet)
        section_headings = {s.heading for s in doc.sections}
        assert "Inventory" in section_headings
        assert "Raw Data" in section_headings

    async def test_multi_sheet_content_populated(self, xlsx_multi_sheet: str) -> None:
        pytest.importorskip("openpyxl")
        doc = await self.parser.parse(xlsx_multi_sheet)
        assert not doc.is_empty
        assert len(doc.content) > 0

    async def test_multi_sheet_section_headings_are_level_1(self, xlsx_multi_sheet: str) -> None:
        pytest.importorskip("openpyxl")
        doc = await self.parser.parse(xlsx_multi_sheet)
        for section in doc.sections:
            assert section.level == 1

    async def test_multi_sheet_section_page_number_is_none(self, xlsx_multi_sheet: str) -> None:
        pytest.importorskip("openpyxl")
        doc = await self.parser.parse(xlsx_multi_sheet)
        for section in doc.sections:
            assert section.page_number is None

    async def test_header_row_heuristic_applied(self, xlsx_single_sheet: str) -> None:
        """When first row is all strings, cells should appear as key: value pairs."""
        pytest.importorskip("openpyxl")
        doc = await self.parser.parse(xlsx_single_sheet)
        # With header detection, content should include "Name: Alice" style pairs.
        assert "Name" in doc.content
        assert "Alice" in doc.content

    # ── Empty sheet ──────────────────────────────────────────────────────────

    async def test_empty_sheet_returns_empty_document(self, xlsx_empty_sheet: str) -> None:
        pytest.importorskip("openpyxl")
        doc = await self.parser.parse(xlsx_empty_sheet)
        assert doc.is_empty is True
        assert doc.sections == []

    # ── File type and name ───────────────────────────────────────────────────

    async def test_file_type_is_xlsx(self, xlsx_single_sheet: str) -> None:
        pytest.importorskip("openpyxl")
        doc = await self.parser.parse(xlsx_single_sheet)
        assert doc.file_type == ".xlsx"

    async def test_file_name_set(self, xlsx_single_sheet: str) -> None:
        pytest.importorskip("openpyxl")
        doc = await self.parser.parse(xlsx_single_sheet)
        assert doc.file_name.endswith(".xlsx")


# ===========================================================================
# PdfParser
# ===========================================================================


class TestPdfParser:
    """Tests for :class:`app.parsers.pdf_parser.PdfParser`."""

    def setup_method(self) -> None:
        self.parser = PdfParser()

    # ── supported_extensions ────────────────────────────────────────────────

    def test_supported_extensions_contains_pdf(self) -> None:
        assert ".pdf" in self.parser.supported_extensions

    # ── supports() ──────────────────────────────────────────────────────────

    def test_supports_pdf_extension(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "doc.pdf"
        p.touch()
        assert self.parser.supports(str(p)) is True

    def test_does_not_support_docx(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "doc.docx"
        p.touch()
        assert self.parser.supports(str(p)) is False

    def test_does_not_support_md(self, tmp_path: "os.PathLike[str]") -> None:
        p = tmp_path / "readme.md"
        p.touch()
        assert self.parser.supports(str(p)) is False

    # ── File-not-found ───────────────────────────────────────────────────────

    async def test_file_not_found_raises_parser_error(self, nonexistent_file: str) -> None:
        with pytest.raises(ParserError) as exc_info:
            await self.parser.parse(nonexistent_file)
        assert exc_info.value.file_path == nonexistent_file

    # ── Corrupt file ─────────────────────────────────────────────────────────

    async def test_corrupt_pdf_raises_parser_error(self, pdf_corrupt: str) -> None:
        pytest.importorskip("fitz")
        with pytest.raises(ParserError) as exc_info:
            await self.parser.parse(pdf_corrupt)
        assert exc_info.value.file_path == pdf_corrupt

    # ── Single-page PDF ──────────────────────────────────────────────────────

    async def test_single_page_page_count(self, pdf_single_page: str) -> None:
        pytest.importorskip("fitz")
        doc = await self.parser.parse(pdf_single_page)
        assert doc.page_count == 1

    async def test_single_page_content_not_empty(self, pdf_single_page: str) -> None:
        pytest.importorskip("fitz")
        doc = await self.parser.parse(pdf_single_page)
        assert not doc.is_empty
        assert "Hello" in doc.content or "page" in doc.content.lower()

    async def test_single_page_pages_list_populated(self, pdf_single_page: str) -> None:
        pytest.importorskip("fitz")
        doc = await self.parser.parse(pdf_single_page)
        assert len(doc.pages) == 1
        assert isinstance(doc.pages[0], PageContent)
        assert doc.pages[0].page_number == 1

    # ── Multi-page PDF ───────────────────────────────────────────────────────

    async def test_multi_page_page_count(self, pdf_multi_page: str) -> None:
        pytest.importorskip("fitz")
        doc = await self.parser.parse(pdf_multi_page)
        assert doc.page_count == 3

    async def test_multi_page_pages_list_length(self, pdf_multi_page: str) -> None:
        pytest.importorskip("fitz")
        doc = await self.parser.parse(pdf_multi_page)
        assert len(doc.pages) == 3

    async def test_multi_page_page_numbers_sequential(self, pdf_multi_page: str) -> None:
        pytest.importorskip("fitz")
        doc = await self.parser.parse(pdf_multi_page)
        page_numbers = [p.page_number for p in doc.pages]
        assert page_numbers == [1, 2, 3]

    async def test_multi_page_all_text_in_content(self, pdf_multi_page: str) -> None:
        pytest.importorskip("fitz")
        doc = await self.parser.parse(pdf_multi_page)
        # Each page has "Content of page N" — at least page 1 should appear.
        assert "page 1" in doc.content.lower() or "content" in doc.content.lower()

    # ── File type and name ───────────────────────────────────────────────────

    async def test_file_type_is_pdf(self, pdf_single_page: str) -> None:
        pytest.importorskip("fitz")
        doc = await self.parser.parse(pdf_single_page)
        # PdfParser stores file_type without the leading dot ("pdf" not ".pdf").
        assert doc.file_type.lstrip(".") == "pdf"

    async def test_file_name_set(self, pdf_single_page: str) -> None:
        pytest.importorskip("fitz")
        doc = await self.parser.parse(pdf_single_page)
        assert doc.file_name.endswith(".pdf")

    # ── Metadata ─────────────────────────────────────────────────────────────

    async def test_metadata_dict_present(self, pdf_single_page: str) -> None:
        pytest.importorskip("fitz")
        doc = await self.parser.parse(pdf_single_page)
        assert isinstance(doc.metadata, dict)
