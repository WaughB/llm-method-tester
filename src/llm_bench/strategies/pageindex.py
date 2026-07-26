"""PageIndex-style vectorless retrieval: heading trees + LLM reasoning traversal.

A faithful reimplementation of the PageIndex method by VectifyAI
(https://github.com/VectifyAI/PageIndex, MIT license): documents become
TOC-like trees, and instead of vector similarity, the model *reasons* over the
tree outline to decide which sections to read, then descends one level to
refine. Costs 2-3 LLM calls per question — that cost is part of the benchmark.
"""

import json
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.documents import Document
from llm_bench.corpus.qa import Question
from llm_bench.llm.base import GenOptions, LLMClient
from llm_bench.llm.jsonutil import extract_json
from llm_bench.strategies.base import ANSWER_SYSTEM, RetrievalStrategy, StrategyAnswer

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")

SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "node_ids": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
    },
    "required": ["node_ids"],
}

_SELECT_TEMPLATE = """You are navigating a table of contents of technical documents \
to locate sections that answer a question.

Question: {question}

Document tree (one node per line: [id] title - summary):
{outline}

Select up to {k} node ids whose sections most likely contain the answer. \
Respond with JSON: {{"node_ids": [...], "reasoning": "..."}}"""

_REFINE_TEMPLATE = """Refine your selection. You chose sections that have more specific \
subsections. Question: {question}

Subsections:
{outline}

Choose up to {k} of these subsection node ids that best answer the question. \
Respond with JSON: {{"node_ids": [...], "reasoning": "..."}}"""

_ANSWER_TEMPLATE = """Use the following document sections to answer the question.

{context}

Question: {question}

Answer concisely using only the sections above."""

_SUMMARY_TEMPLATE = """Summarize this section in one or two sentences for a table of contents.

Section title: {title}

{text}"""


@dataclass
class TreeNode:
    node_id: str
    doc_id: str
    title: str
    level: int
    text: str
    children: list["TreeNode"] = field(default_factory=list)


def build_forest(documents: Iterable[Document]) -> list[TreeNode]:
    """One tree per document from its heading hierarchy; ids follow DFS order."""
    roots = [_build_tree(doc) for doc in documents]
    counter = 0

    def assign(node: TreeNode) -> None:
        nonlocal counter
        counter += 1
        node.node_id = f"n{counter:04d}"
        for child in node.children:
            assign(child)

    for root in roots:
        assign(root)
    return roots


def _build_tree(doc: Document) -> TreeNode:
    virtual_root = TreeNode(node_id="", doc_id=doc.doc_id, title=doc.title, level=0, text="")
    stack = [virtual_root]
    current = virtual_root
    for line in doc.text.splitlines():
        match = _HEADING_RE.match(line)
        if match is None:
            current.text += line + "\n"
            continue
        level = len(match.group(1))
        node = TreeNode(
            node_id="", doc_id=doc.doc_id, title=match.group(2).strip(), level=level, text=""
        )
        while len(stack) > 1 and stack[-1].level >= level:
            stack.pop()
        stack[-1].children.append(node)
        stack.append(node)
        current = node
    for node in [virtual_root, *virtual_root.children]:
        node.text = node.text.strip()
    # collapse the virtual root when the doc has a single top-level heading
    if len(virtual_root.children) == 1 and not virtual_root.text:
        return virtual_root.children[0]
    return virtual_root


def subtree_text(node: TreeNode) -> str:
    parts = [f"{node.title}\n{node.text}".strip()]
    parts.extend(subtree_text(child) for child in node.children)
    return "\n\n".join(p for p in parts if p)


def _walk(nodes: Iterable[TreeNode]) -> Iterable[TreeNode]:
    for node in nodes:
        yield node
        yield from _walk(node.children)


class PageIndexStrategy(RetrievalStrategy):
    name: ClassVar[str] = "pageindex"
    representation: ClassVar[str | None] = "docs"

    def __init__(
        self,
        llm: LLMClient,
        cache_dir: Path,
        *,
        max_select: int = 4,
        options: GenOptions | None = None,
    ) -> None:
        self._llm = llm
        self._cache_dir = cache_dir
        self._max_select = max_select
        # The tree outline is by far the largest prompt in the benchmark; the
        # default 8k context silently truncates it and the model selects nothing.
        self._options = options or GenOptions(num_ctx=16384)
        self._forest: list[TreeNode] = []
        self._nodes: dict[str, TreeNode] = {}
        self._summaries: dict[str, str] = {}

    def prepare(self, corpus: BenchmarkCorpus, model: str) -> None:
        self._forest = build_forest(corpus.documents)
        self._nodes = {n.node_id: n for n in _walk(self._forest)}
        cache_file = self._cache_file(corpus, model)
        if cache_file.exists():
            self._summaries = json.loads(cache_file.read_text(encoding="utf-8"))
            if set(self._summaries) == set(self._nodes):
                return
        self._summaries = {
            node.node_id: self._summarize(node, model) for node in self._nodes.values()
        }
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(self._summaries, indent=1), encoding="utf-8")

    def _cache_file(self, corpus: BenchmarkCorpus, model: str) -> Path:
        safe_model = re.sub(r"[^A-Za-z0-9._-]", "-", model)
        return self._cache_dir / "pageindex" / f"{safe_model}_{corpus.content_hash()}.json"

    def _summarize(self, node: TreeNode, model: str) -> str:
        prompt = _SUMMARY_TEMPLATE.format(title=node.title, text=node.text[:4000])
        response = self._llm.generate(model, prompt, options=self._options)
        return response.text.strip()

    def answer(self, question: Question, model: str) -> StrategyAnswer:
        if not self._nodes:
            raise RuntimeError("prepare() must be called before answer()")
        start = time.perf_counter()
        llm_calls = 0
        prompt_tokens = completion_tokens = 0

        # First pass sees roots + H2 sections only (PageIndex descends rather
        # than dumping the whole tree); deeper nodes appear in the refinement.
        outline = "\n".join(self._outline_lines(self._forest, depth=0, max_depth=1))
        select_prompt = _SELECT_TEMPLATE.format(
            question=question.question, outline=outline, k=self._max_select
        )
        response = self._llm.generate(
            model, select_prompt, json_schema=SELECT_SCHEMA, options=self._options
        )
        llm_calls += 1
        prompt_tokens += response.prompt_tokens
        completion_tokens += response.completion_tokens
        selected = self._parse_selection(response.text)

        parents = [n for n in selected if n.children]
        if parents:
            child_outline = "\n".join(self._outline_lines(parents, depth=0, children_only=True))
            refine_prompt = _REFINE_TEMPLATE.format(
                question=question.question, outline=child_outline, k=self._max_select
            )
            response = self._llm.generate(
                model, refine_prompt, json_schema=SELECT_SCHEMA, options=self._options
            )
            llm_calls += 1
            prompt_tokens += response.prompt_tokens
            completion_tokens += response.completion_tokens
            refined = self._parse_selection(response.text)
            leaves = [n for n in selected if not n.children]
            if refined:
                selected = leaves + refined

        context = "\n\n---\n\n".join(subtree_text(n) for n in selected)
        answer_prompt = _ANSWER_TEMPLATE.format(context=context, question=question.question)
        response = self._llm.generate(
            model, answer_prompt, system=ANSWER_SYSTEM, options=self._options
        )
        llm_calls += 1
        prompt_tokens += response.prompt_tokens
        completion_tokens += response.completion_tokens

        latency_ms = (time.perf_counter() - start) * 1000
        retrieved_ids = list(dict.fromkeys(n.doc_id for n in selected))
        return StrategyAnswer(
            text=response.text,
            retrieved_ids=retrieved_ids,
            llm_calls=llm_calls,
            latency_ms=latency_ms,
            tokens_per_sec=response.tokens_per_sec,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            context_chars=len(context),
        )

    def _outline_lines(
        self,
        nodes: Iterable[TreeNode],
        depth: int,
        max_depth: int | None = None,
        children_only: bool = False,
    ) -> list[str]:
        lines: list[str] = []
        for node in nodes:
            if children_only:
                lines.append(f"[{node.node_id}] {node.title} (context: parent section)")
                lines.extend(self._outline_lines(node.children, depth + 1))
                continue
            summary = self._summaries.get(node.node_id, "")
            lines.append(f"{'  ' * depth}[{node.node_id}] {node.title} - {summary}")
            if max_depth is None or depth < max_depth:
                lines.extend(self._outline_lines(node.children, depth + 1, max_depth))
        return lines

    def _parse_selection(self, text: str) -> list[TreeNode]:
        data = extract_json(text)
        if data is None:
            return []
        ids = [str(i) for i in data.get("node_ids", []) or []]
        return [self._nodes[i] for i in ids if i in self._nodes][: self._max_select]
