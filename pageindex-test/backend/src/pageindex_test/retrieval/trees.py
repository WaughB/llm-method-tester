"""PageIndex precision stage: lazy per-document trees + LLM section selection.

Trees are built from each retrieved document's extracted markdown using the
benchmark's `build_forest`, cached on disk keyed by content hash. Unlike the
benchmark, outlines carry deterministic text previews instead of LLM-written
summaries — query-time indexing must be cheap, and the cache stays
model-independent.

The token guard is non-negotiable project history: Ollama silently truncates
over-budget prompts (we measured a model answering an *invented* question),
so an over-budget outline triggers a VISIBLE fallback recorded in the trace,
never a silent truncation.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field

from llm_bench.corpus.documents import Document
from llm_bench.llm.base import GenOptions, LLMClient
from llm_bench.llm.jsonutil import extract_json
from llm_bench.strategies.pageindex import TreeNode, build_forest, subtree_text

from pageindex_test.pipeline.query import Citation

logger = logging.getLogger("pageindex_test.trees")

SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "node_ids": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
    },
    "required": ["node_ids"],
}

_SELECT_TEMPLATE = """You are navigating tables of contents of the user's documents \
to locate sections that answer a question.

Question: {question}

Document tree (one node per line: [id] title - preview):
{outline}

Select up to {k} node ids whose sections most likely contain the answer. \
Respond with JSON: {{"node_ids": [...], "reasoning": "..."}}"""

_PREVIEW_CHARS = 120


class TreeStageOverBudget(Exception):
    """Outline exceeds the model context budget; caller must fall back visibly."""


@dataclass
class TreeStageResult:
    context: str
    citations: list[Citation]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_calls: int = 0
    fallback: bool = False


@dataclass
class CachedTree:
    doc_id: str
    title: str
    roots: list[TreeNode] = field(default_factory=list)


class TreeStage:
    def __init__(
        self,
        llm: LLMClient,
        tree_cache_dir_resolver,  # Callable[[location_id], Path]
        extracted_path_resolver,  # Callable[[location_id, doc_id], Path]
        doc_title_resolver,  # Callable[[doc_id], str]
        *,
        max_docs: int = 4,
        max_select: int = 4,
        num_ctx: int = 16384,
    ) -> None:
        self._llm = llm
        self._tree_cache_dir = tree_cache_dir_resolver
        self._extracted_path = extracted_path_resolver
        self._doc_title = doc_title_resolver
        self._max_docs = max_docs
        self._max_select = max_select
        self._num_ctx = num_ctx

    # -- tree building -------------------------------------------------------

    def get_or_build_forest(self, location_id: str, doc_id: str) -> list[TreeNode]:
        source = self._extracted_path(location_id, doc_id)
        if not source.exists():
            return []
        text = source.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        cache_file = self._tree_cache_dir(location_id) / f"{doc_id}_{content_hash}.json"
        if cache_file.exists():
            return [_node_from_dict(d) for d in json.loads(cache_file.read_text(encoding="utf-8"))]
        forest = build_forest([Document(doc_id=doc_id, title=self._doc_title(doc_id), text=text)])
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps([_node_to_dict(n) for n in forest]), encoding="utf-8")
        return forest

    # -- the stage -----------------------------------------------------------

    def run(self, recorder, location_id: str, question: str, model: str, fused) -> TreeStageResult:
        from pageindex_test.retrieval.fusion import top_docs

        with recorder.stage("tree_build") as stage:
            doc_ids = top_docs(fused, self._max_docs)
            nodes: dict[str, tuple[str, TreeNode]] = {}
            forests: list[tuple[str, list[TreeNode]]] = []
            counter = 0
            for doc_id in doc_ids:
                forest = self.get_or_build_forest(location_id, doc_id)
                for node in _walk_all(forest):
                    counter += 1
                    node.node_id = f"n{counter:04d}"
                    nodes[node.node_id] = (doc_id, node)
                if forest:
                    forests.append((doc_id, forest))
            stage.candidates = len(nodes)
            stage.detail = {"docs": doc_ids}

        if not nodes:
            raise TreeStageOverBudget("No trees available for retrieved documents")

        outline = "\n".join(self._outline_lines(forests))
        prompt = _SELECT_TEMPLATE.format(question=question, outline=outline, k=self._max_select)
        estimated_tokens = len(prompt) // 3  # conservative chars-per-token
        if estimated_tokens > int(self._num_ctx * 0.8):
            raise TreeStageOverBudget(
                f"Tree outline ~{estimated_tokens} tokens exceeds the "
                f"{self._num_ctx} context budget"
            )

        with recorder.stage("tree_select") as stage:
            response = self._llm.generate(
                model,
                prompt,
                json_schema=SELECT_SCHEMA,
                options=GenOptions(num_ctx=self._num_ctx),
            )
            parsed = extract_json(response.text) or {}
            selected_ids = [str(i) for i in (parsed.get("node_ids") or [])][: self._max_select]
            selected = [nodes[i] for i in selected_ids if i in nodes]
            stage.candidates = len(selected)
            stage.tokens = response.prompt_tokens + response.completion_tokens
            stage.detail = {
                "selected": [{"doc_id": doc_id, "title": node.title} for doc_id, node in selected],
                "reasoning": str(parsed.get("reasoning", ""))[:500],
            }

        if not selected:
            raise TreeStageOverBudget("Tree selection returned no usable sections")

        context = "\n\n---\n\n".join(subtree_text(node) for _, node in selected)
        citations = [
            Citation(
                doc_id=doc_id,
                chunk_id=None,
                heading=node.title,
                snippet=(node.text or subtree_text(node))[:240],
            )
            for doc_id, node in selected
        ]
        return TreeStageResult(
            context=context,
            citations=citations,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            llm_calls=1,
        )

    def _outline_lines(self, forests: list[tuple[str, list[TreeNode]]]) -> list[str]:
        lines: list[str] = []

        def walk(node: TreeNode, depth: int) -> None:
            preview = " ".join((node.text or "").split())[:_PREVIEW_CHARS]
            lines.append(f"{'  ' * depth}[{node.node_id}] {node.title} - {preview}")
            for child in node.children:
                walk(child, depth + 1)

        for _doc_id, forest in forests:
            for root in forest:
                walk(root, 0)
        return lines


def _walk_all(forest: list[TreeNode]):
    for root in forest:
        yield root
        yield from _walk_all(root.children)


def _node_to_dict(node: TreeNode) -> dict:
    return {
        "node_id": node.node_id,
        "doc_id": node.doc_id,
        "title": node.title,
        "level": node.level,
        "text": node.text,
        "children": [_node_to_dict(c) for c in node.children],
    }


def _node_from_dict(data: dict) -> TreeNode:
    return TreeNode(
        node_id=data["node_id"],
        doc_id=data["doc_id"],
        title=data["title"],
        level=data["level"],
        text=data["text"],
        children=[_node_from_dict(c) for c in data["children"]],
    )
