"""Corpus loading: plain documents, Obsidian vault, and the combined bundle."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from llm_bench.corpus.documents import DocumentCorpus
from llm_bench.corpus.vault import Vault

__all__ = ["BenchmarkCorpus", "DocumentCorpus", "Vault"]


@dataclass(frozen=True)
class BenchmarkCorpus:
    """Both representations of the benchmark facts: plain docs and vault notes."""

    root: Path
    documents: DocumentCorpus
    vault: Vault

    @classmethod
    def load(cls, root: Path) -> "BenchmarkCorpus":
        return cls(root=root, documents=DocumentCorpus.load(root), vault=Vault.load(root))

    def content_hash(self) -> str:
        """Short stable digest of all corpus text; used to key index caches."""
        digest = hashlib.sha256()
        for doc in self.documents:
            digest.update(doc.doc_id.encode("utf-8"))
            digest.update(doc.text.encode("utf-8"))
        for note in self.vault:
            digest.update(note.note_id.encode("utf-8"))
            digest.update(note.body.encode("utf-8"))
        return digest.hexdigest()[:16]
