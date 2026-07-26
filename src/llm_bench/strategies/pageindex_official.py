"""The OFFICIAL PageIndex implementation, driven verbatim.

Indexing calls `md_to_tree` from the vendored VectifyAI/PageIndex code
(commit 190f8b3, MIT) — their markdown tree builder with their LLM-generated
node summaries via LiteLLM. Retrieval reproduces their canonical cookbook flow
(`cookbook/pageindex_RAG_simple.ipynb`): their search prompt over the
text-stripped tree JSON, their `utils.extract_json` parsing, their answer
prompt over the selected nodes' text.

Adaptations required to run it in this benchmark (disclosed in the README):
- the cookbook is single-document, so the search prompt receives a JSON list
  of per-document trees and node ids are renumbered to be unique across
  documents (same 4-digit format their `if_add_node_id` produces);
- models are addressed as `ollama/<name>` through LiteLLM, exactly as their
  utils supports.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import ClassVar

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import Question
from llm_bench.strategies.base import RetrievalStrategy, StrategyAnswer

# Their exact prompt texts from cookbook/pageindex_RAG_simple.ipynb.
_SEARCH_PROMPT = """
You are given a question and a tree structure of a document.
Each node contains a node id, node title, and a corresponding summary.
Your task is to find all nodes that are likely to contain the answer to the question.

Question: {query}

Document tree structure:
{tree_json}

Please reply in the following JSON format:
{{
    "thinking": "<Your thinking process on which nodes are relevant to the question>",
    "node_list": ["node_id_1", "node_id_2", ..., "node_id_n"]
}}
Directly return the final JSON structure. Do not output anything else.
"""

_ANSWER_PROMPT = """
Answer the question based on the context:

Question: {query}
Context: {relevant_content}

Provide a clear, concise answer based only on the context provided.
"""


class PageIndexOfficialStrategy(RetrievalStrategy):
    name: ClassVar[str] = "pageindex_official"
    representation: ClassVar[str | None] = "docs"

    def __init__(
        self,
        cache_dir: Path,
        ollama_base_url: str = "http://localhost:11434",
        *,
        num_ctx: int = 16384,
    ) -> None:
        self._cache_dir = cache_dir
        self._api_base = ollama_base_url
        self._num_ctx = num_ctx
        self._trees: list[dict] = []  # [{doc_id, doc_name, structure}]
        self._node_map: dict[str, tuple[str, dict]] = {}  # node_id -> (doc_id, node)

    def prepare(self, corpus: BenchmarkCorpus, model: str) -> None:
        import os

        os.environ.setdefault("OLLAMA_API_BASE", self._api_base)
        cache_file = self._cache_file(corpus, model)
        if cache_file.exists():
            self._trees = json.loads(cache_file.read_text(encoding="utf-8"))
        else:
            self._trees = self._build_trees(corpus, model)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps(self._trees, ensure_ascii=False), encoding="utf-8"
            )
        self._node_map = self._renumber_nodes(self._trees)

    def _cache_file(self, corpus: BenchmarkCorpus, model: str) -> Path:
        import re

        safe_model = re.sub(r"[^A-Za-z0-9._-]", "-", model)
        return (
            self._cache_dir
            / "pageindex_official"
            / f"{safe_model}_{corpus.content_hash()}.json"
        )

    def _build_trees(self, corpus: BenchmarkCorpus, model: str) -> list[dict]:
        """Run their md_to_tree verbatim on every corpus document."""
        from llm_bench._vendor.pageindex.page_index_md import md_to_tree

        trees = []
        for doc in corpus.documents:
            md_path = corpus.root / doc.doc_id
            result = asyncio.run(
                md_to_tree(
                    md_path=str(md_path),
                    if_thinning=False,
                    if_add_node_summary="yes",
                    summary_token_threshold=200,
                    model=f"ollama/{model}",
                    if_add_doc_description="no",
                    if_add_node_text="yes",
                    if_add_node_id="yes",
                )
            )
            trees.append(
                {
                    "doc_id": doc.doc_id,
                    "doc_name": result.get("doc_name", doc.title),
                    "structure": result["structure"],
                }
            )
        return trees

    @staticmethod
    def _renumber_nodes(trees: list[dict]) -> dict[str, tuple[str, dict]]:
        """Make node ids unique across documents (their per-doc ids collide).

        Keeps their 4-digit format; pure bookkeeping, no structural change.
        """
        node_map: dict[str, tuple[str, dict]] = {}
        counter = 0

        def walk(nodes: list[dict], doc_id: str) -> None:
            nonlocal counter
            for node in nodes:
                node["node_id"] = f"{counter:04d}"
                node_map[node["node_id"]] = (doc_id, node)
                counter += 1
                walk(node.get("nodes") or [], doc_id)

        for tree in trees:
            walk(tree["structure"], tree["doc_id"])
        return node_map

    def answer(self, question: Question, model: str) -> StrategyAnswer:
        from llm_bench._vendor.pageindex.utils import extract_json, remove_fields

        if not self._node_map:
            raise RuntimeError("prepare() must be called before answer()")
        start = time.perf_counter()
        prompt_tokens = completion_tokens = 0

        documents_json = json.dumps(
            [
                {
                    "doc_name": t["doc_name"],
                    "structure": remove_fields(
                        json.loads(json.dumps(t["structure"])), fields=["text"]
                    ),
                }
                for t in self._trees
            ],
            indent=2,
        )
        search_prompt = _SEARCH_PROMPT.format(query=question.question, tree_json=documents_json)
        text, usage = self._call_llm(model, search_prompt)
        prompt_tokens += usage[0]
        completion_tokens += usage[1]
        parsed = extract_json(text) or {}
        node_ids = [str(n) for n in (parsed.get("node_list") or [])]
        selected = [(nid, *self._node_map[nid]) for nid in node_ids if nid in self._node_map]

        relevant_content = "\n\n".join(node.get("text") or "" for _, _, node in selected)
        answer_prompt = _ANSWER_PROMPT.format(
            query=question.question, relevant_content=relevant_content
        )
        gen_start = time.perf_counter()
        answer_text, usage = self._call_llm(model, answer_prompt)
        gen_secs = max(time.perf_counter() - gen_start, 1e-6)
        prompt_tokens += usage[0]
        completion_tokens += usage[1]

        latency_ms = (time.perf_counter() - start) * 1000
        retrieved_ids = list(dict.fromkeys(doc_id for _, doc_id, _ in selected))
        return StrategyAnswer(
            text=answer_text.strip(),
            retrieved_ids=retrieved_ids,
            llm_calls=2,
            latency_ms=latency_ms,
            tokens_per_sec=usage[1] / gen_secs,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            context_chars=len(relevant_content),
        )

    def _call_llm(self, model: str, prompt: str) -> tuple[str, tuple[int, int]]:
        """One chat call the way their cookbook does it (temperature 0)."""
        import litellm

        response = litellm.completion(
            model=f"ollama/{model}",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            api_base=self._api_base,
            num_ctx=self._num_ctx,
        )
        usage = getattr(response, "usage", None)
        tokens = (
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
        )
        return response.choices[0].message.content or "", tokens
