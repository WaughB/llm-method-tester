"""Format extraction to markdown-ish text.

Everything downstream (chunker, BM25, PageIndex trees) consumes markdown with
headings, so extraction's job is to produce the best heading structure the
source allows: PDFs get their table of contents injected as `#` headings when
one exists, else per-page `## Page N` markers; TXT becomes one titled section.
Image-only (scanned) PDFs are rejected loudly — silent empty text would
poison retrieval.
"""

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_SUFFIXES = {".pdf", ".md", ".markdown", ".txt"}
_SCANNED_CHARS_PER_PAGE = 25


class UnsupportedDocumentError(Exception):
    """Raised when a document cannot produce usable text (with a reason)."""


@dataclass(frozen=True)
class ExtractedDoc:
    markdown: str
    title: str
    format: str  # pdf | md | txt
    pages: int | None = None


def extract(path: Path) -> ExtractedDoc:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise UnsupportedDocumentError(
            f"Unsupported file type {suffix!r} — supported: PDF, Markdown, TXT"
        )
    if suffix in (".md", ".markdown"):
        return _extract_markdown(path)
    if suffix == ".txt":
        return _extract_txt(path)
    return _extract_pdf(path)


def _extract_markdown(path: Path) -> ExtractedDoc:
    text = path.read_text(encoding="utf-8", errors="replace")
    title = path.stem
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return ExtractedDoc(markdown=text, title=title, format="md")


def _extract_txt(path: Path) -> ExtractedDoc:
    body = path.read_text(encoding="utf-8", errors="replace").strip()
    if not body:
        raise UnsupportedDocumentError("File is empty")
    return ExtractedDoc(markdown=f"# {path.stem}\n\n{body}\n", title=path.stem, format="txt")


def _extract_pdf(path: Path) -> ExtractedDoc:
    import pymupdf

    with pymupdf.open(path) as pdf:
        page_texts = [page.get_text() for page in pdf]
        page_count = len(page_texts)
        if page_count == 0:
            raise UnsupportedDocumentError("PDF has no pages")
        total_chars = sum(len(t.strip()) for t in page_texts)
        if total_chars / page_count < _SCANNED_CHARS_PER_PAGE:
            raise UnsupportedDocumentError(
                "PDF appears to be scanned (almost no extractable text; "
                f"{total_chars} chars across {page_count} pages). OCR is not supported."
            )
        toc = pdf.get_toc()  # [[level, title, page], ...]
        title = (pdf.metadata or {}).get("title") or path.stem

    headings_by_page: dict[int, list[tuple[int, str]]] = {}
    for level, heading, page_no in toc:
        headings_by_page.setdefault(page_no, []).append((min(level, 6), heading.strip()))

    lines: list[str] = [f"# {title}", ""]
    for page_no, text in enumerate(page_texts, start=1):
        if toc:
            for level, heading in headings_by_page.get(page_no, []):
                lines.append(f"{'#' * max(2, level + 1)} {heading}")
                lines.append("")
        else:
            lines.append(f"## Page {page_no}")
            lines.append("")
        cleaned = text.strip()
        if cleaned:
            lines.append(cleaned)
            lines.append("")
    return ExtractedDoc(markdown="\n".join(lines), title=title, format="pdf", pages=page_count)
