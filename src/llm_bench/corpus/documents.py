"""Plain markdown document corpus (the input for vector RAG and PageIndex)."""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Document:
    doc_id: str  # posix path relative to corpus root, e.g. "docs/api.md"
    title: str
    text: str


class DocumentCorpus:
    def __init__(self, documents: list[Document]) -> None:
        self._documents = sorted(documents, key=lambda d: d.doc_id)
        self._by_id = {d.doc_id: d for d in self._documents}

    @classmethod
    def load(cls, corpus_root: Path) -> "DocumentCorpus":
        docs_dir = corpus_root / "docs"
        documents = []
        for path in sorted(docs_dir.rglob("*.md")) if docs_dir.exists() else []:
            text = path.read_text(encoding="utf-8")
            match = _H1_RE.search(text)
            title = match.group(1).strip() if match else path.stem
            doc_id = path.relative_to(corpus_root).as_posix()
            documents.append(Document(doc_id=doc_id, title=title, text=text))
        return cls(documents)

    def get(self, doc_id: str) -> Document:
        return self._by_id[doc_id]

    def __iter__(self) -> Iterator[Document]:
        return iter(self._documents)

    def __len__(self) -> int:
        return len(self._documents)
