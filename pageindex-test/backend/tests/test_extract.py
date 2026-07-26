"""Extraction tests: md, txt, PDF (with TOC / without / scanned)."""

from pathlib import Path

import pytest

from conftest import make_pdf
from pageindex_test.ingest.extract import UnsupportedDocumentError, extract


class TestMarkdown:
    def test_passthrough_with_title(self, tmp_path: Path) -> None:
        source = tmp_path / "notes.md"
        source.write_text("# My Notes\n\n## Section\n\nBody.", encoding="utf-8")
        result = extract(source)
        assert result.title == "My Notes"
        assert result.format == "md"
        assert "## Section" in result.markdown

    def test_title_falls_back_to_stem(self, tmp_path: Path) -> None:
        source = tmp_path / "untitled.md"
        source.write_text("no headings here", encoding="utf-8")
        assert extract(source).title == "untitled"


class TestTxt:
    def test_wrapped_with_title_heading(self, tmp_path: Path) -> None:
        source = tmp_path / "readme.txt"
        source.write_text("plain text content\n\nsecond paragraph", encoding="utf-8")
        result = extract(source)
        assert result.markdown.startswith("# readme")
        assert "second paragraph" in result.markdown

    def test_empty_txt_unsupported(self, tmp_path: Path) -> None:
        source = tmp_path / "empty.txt"
        source.write_text("   ", encoding="utf-8")
        with pytest.raises(UnsupportedDocumentError, match="empty"):
            extract(source)


class TestPdf:
    def test_pdf_with_toc_gets_heading_structure(self, tmp_path: Path) -> None:
        source = make_pdf(
            tmp_path / "doc.pdf",
            pages=["Introduction text here " * 10, "Methods text here " * 10],
            toc=[[1, "Introduction", 1], [1, "Methods", 2]],
        )
        result = extract(source)
        assert result.format == "pdf"
        assert result.pages == 2
        assert "## Introduction" in result.markdown
        assert "## Methods" in result.markdown
        assert "Page 1" not in result.markdown  # toc mode, not page mode

    def test_pdf_without_toc_gets_page_headings(self, tmp_path: Path) -> None:
        source = make_pdf(tmp_path / "plain.pdf", pages=["Some long text " * 20])
        result = extract(source)
        assert "## Page 1" in result.markdown

    def test_scanned_pdf_rejected_with_reason(self, tmp_path: Path) -> None:
        source = make_pdf(tmp_path / "scan.pdf", pages=["", "", ""])
        with pytest.raises(UnsupportedDocumentError, match="scanned"):
            extract(source)


class TestUnsupported:
    def test_unknown_suffix(self, tmp_path: Path) -> None:
        source = tmp_path / "sheet.xlsx"
        source.write_text("x", encoding="utf-8")
        with pytest.raises(UnsupportedDocumentError, match="Unsupported file type"):
            extract(source)
