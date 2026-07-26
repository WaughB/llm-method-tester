"""Obsidian-style RAG: lexical seeding plus knowledge-graph traversal.

Retrieval mirrors how an Obsidian user hops through their vault: find the
lexically relevant notes (BM25 over weighted title/tags/body), then follow
wikilinks and backlinks one hop out, boosting neighbors that share tags.
Retrieval is fully deterministic — the LLM only generates the final answer.
"""

import re
import time
from typing import ClassVar

from rank_bm25 import BM25Okapi

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import Question
from llm_bench.corpus.vault import Vault, VaultNote
from llm_bench.llm.base import GenOptions, LLMClient
from llm_bench.strategies.base import ANSWER_SYSTEM, RetrievalStrategy, StrategyAnswer

_TOKEN_RE = re.compile(r"\w+")

_PROMPT_TEMPLATE = """Use the following notes to answer the question.

{context}

Question: {question}

Answer concisely using only the notes above."""

_LINK_DECAY = 0.5
_SHARED_TAG_BOOST = 0.2


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _note_search_text(note: VaultNote) -> list[str]:
    """Weighted bag: title counts 3x, tags 2x, body 1x."""
    tokens = _tokenize(note.title) * 3
    tokens += [t.lower() for t in note.tags] * 2
    tokens += _tokenize(note.body)
    return tokens


class ObsidianRAGStrategy(RetrievalStrategy):
    name: ClassVar[str] = "obsidian_rag"
    representation: ClassVar[str | None] = "vault"

    def __init__(
        self,
        llm: LLMClient,
        *,
        seed_k: int = 3,
        max_notes: int = 6,
        options: GenOptions | None = None,
    ) -> None:
        self._llm = llm
        self._seed_k = seed_k
        self._max_notes = max_notes
        self._options = options or GenOptions()
        self._vault: Vault | None = None
        self._note_ids: list[str] = []
        self._bm25: BM25Okapi | None = None

    def prepare(self, corpus: BenchmarkCorpus, model: str) -> None:
        if self._vault is corpus.vault:
            return  # index is model-independent
        self._vault = corpus.vault
        self._note_ids = [n.note_id for n in corpus.vault]
        self._bm25 = BM25Okapi([_note_search_text(n) for n in corpus.vault])

    def answer(self, question: Question, model: str) -> StrategyAnswer:
        if self._vault is None or self._bm25 is None:
            raise RuntimeError("prepare() must be called before answer()")
        start = time.perf_counter()
        selected = self._retrieve(question.question)
        context = "\n\n".join(self._render_note(self._vault.get(nid)) for nid in selected)
        prompt = _PROMPT_TEMPLATE.format(context=context, question=question.question)
        response = self._llm.generate(model, prompt, system=ANSWER_SYSTEM, options=self._options)
        latency_ms = (time.perf_counter() - start) * 1000
        return StrategyAnswer(
            text=response.text,
            retrieved_ids=selected,
            llm_calls=1,
            latency_ms=latency_ms,
            tokens_per_sec=response.tokens_per_sec,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            context_chars=len(context),
        )

    def _retrieve(self, query: str) -> list[str]:
        assert self._vault is not None and self._bm25 is not None
        raw = self._bm25.get_scores(_tokenize(query))
        top = max(raw) if len(raw) else 0.0
        norm = {
            nid: (score / top if top > 0 else 0.0)
            for nid, score in zip(self._note_ids, raw, strict=True)
        }
        seeds = sorted(
            (nid for nid in self._note_ids if norm[nid] > 0),
            key=lambda nid: norm[nid],
            reverse=True,
        )[: self._seed_k]
        scores = {nid: norm[nid] for nid in seeds}
        for seed in seeds:
            seed_note = self._vault.get(seed)
            neighbors = set(self._vault.outlinks(seed)) | set(self._vault.backlinks(seed))
            for neighbor in neighbors:
                neighbor_note = self._vault.get(neighbor)
                shared_tags = len(seed_note.tags & neighbor_note.tags)
                link_score = _LINK_DECAY * norm[seed] + _SHARED_TAG_BOOST * shared_tags
                candidate = link_score + norm.get(neighbor, 0.0)
                scores[neighbor] = max(scores.get(neighbor, 0.0), candidate)
        ranked = sorted(scores, key=lambda nid: (-scores[nid], nid))
        return ranked[: self._max_notes]

    @staticmethod
    def _render_note(note: VaultNote) -> str:
        location = f"{note.folder}/{note.title}" if note.folder else note.title
        tags = " ".join(sorted(f"#{t}" for t in note.tags))
        return f"--- Note: {location} {tags}\n{note.body.strip()}"
