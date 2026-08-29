"""Document parsers package.

Public surface
--------------
from app.parsers.base import DocumentParser, ParsedDocument, PageContent, SectionContent, ParserError
from app.parsers.chunker import Chunker, TextChunk
"""
from app.parsers.base import (
    DocumentParser,
    PageContent,
    ParsedDocument,
    ParserError,
    SectionContent,
)
from app.parsers.chunker import Chunker, TextChunk
from app.parsers.docx_parser import DocxParser
from app.parsers.excel_parser import ExcelParser
from app.parsers.markdown_parser import MarkdownParser
from app.parsers.pdf_parser import PdfParser

__all__ = [
    "Chunker",
    "DocxParser",
    "DocumentParser",
    "ExcelParser",
    "MarkdownParser",
    "PageContent",
    "ParsedDocument",
    "ParserError",
    "PdfParser",
    "SectionContent",
    "TextChunk",
]
