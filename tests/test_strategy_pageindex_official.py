"""Tests for the official-PageIndex wrapper strategy (vendored code mocked)."""

import json
from pathlib import Path

import pytest

from llm_bench._vendor.pageindex import page_index_md
from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import QADataset
from llm_bench.strategies.pageindex_official import PageIndexOfficialStrategy


def fake_tree_for(md_path: str) -> dict:
    """Canned per-doc trees with per-doc node ids that collide across docs."""
    name = Path(md_path).stem
    return {
        "doc_name": name,
        "structure": [
            {
                "title": name,
                "node_id": "0000",
                "text": f"{name} root text",
                "summary": f"about {name}",
                "nodes": [
                    {
                        "title": f"{name} section",
                        "node_id": "0001",
                        "text": f"{name} section text with facts",
                        "summary": f"{name} details",
                        "nodes": [],
                    }
                ],
            }
        ],
    }


@pytest.fixture
def patched_md_to_tree(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def fake_md_to_tree(md_path: str, **kwargs) -> dict:
        calls.append(md_path)
        return fake_tree_for(md_path)

    monkeypatch.setattr(page_index_md, "md_to_tree", fake_md_to_tree)
    return calls


class ScriptedLiteLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def completion(self, **kwargs):
        self.calls.append(kwargs)
        text = self.responses.pop(0)

        class Usage:
            prompt_tokens = 100
            completion_tokens = 20

        class Message:
            content = text

        class Choice:
            message = Message()

        class Response:
            usage = Usage()
            choices = [Choice()]

        return Response()


@pytest.fixture
def scripted_llm(monkeypatch: pytest.MonkeyPatch) -> ScriptedLiteLLM:
    import litellm

    scripted = ScriptedLiteLLM(
        [
            json.dumps({"thinking": "ops doc looks right", "node_list": ["0005", "n-bogus"]}),
            "The restart downtime is under 2 seconds.",
        ]
    )
    monkeypatch.setattr(litellm, "completion", scripted.completion)
    return scripted


class TestPrepare:
    def test_builds_trees_once_and_caches(
        self,
        mini_corpus: BenchmarkCorpus,
        tmp_path: Path,
        patched_md_to_tree: list[str],
    ) -> None:
        strategy = PageIndexOfficialStrategy(cache_dir=tmp_path)
        strategy.prepare(mini_corpus, "m1")
        assert len(patched_md_to_tree) == 3  # one md_to_tree call per doc
        # fresh instance, same cache dir: loads from cache, no new builds
        strategy2 = PageIndexOfficialStrategy(cache_dir=tmp_path)
        strategy2.prepare(mini_corpus, "m1")
        assert len(patched_md_to_tree) == 3
        assert len(strategy2._node_map) == 6

    def test_node_ids_renumbered_unique_across_docs(
        self,
        mini_corpus: BenchmarkCorpus,
        tmp_path: Path,
        patched_md_to_tree: list[str],
    ) -> None:
        strategy = PageIndexOfficialStrategy(cache_dir=tmp_path)
        strategy.prepare(mini_corpus, "m1")
        # 3 docs x 2 nodes, originally colliding ids 0000/0001 per doc
        assert sorted(strategy._node_map) == [f"{i:04d}" for i in range(6)]
        doc_ids = {doc_id for doc_id, _ in strategy._node_map.values()}
        assert doc_ids == {"docs/api.md", "docs/overview.md", "docs/ops.md"}


class TestAnswer:
    def test_reproduces_cookbook_flow(
        self,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
        tmp_path: Path,
        patched_md_to_tree: list[str],
        scripted_llm: ScriptedLiteLLM,
    ) -> None:
        strategy = PageIndexOfficialStrategy(cache_dir=tmp_path)
        strategy.prepare(mini_corpus, "m1")
        answer = strategy.answer(mini_dataset.get("q003"), "m1")

        assert answer.text == "The restart downtime is under 2 seconds."
        assert answer.llm_calls == 2
        # node 0005 belongs to the third doc (sorted order: api, ops, overview)
        assert answer.retrieved_ids == ["docs/overview.md"]
        assert answer.context_chars > 0

        search_call = scripted_llm.calls[0]
        prompt = search_call["messages"][0]["content"]
        # their exact prompt language
        assert "find all nodes that are likely to contain the answer" in prompt
        assert "Directly return the final JSON structure" in prompt
        assert mini_dataset.get("q003").question in prompt
        # tree JSON is text-stripped
        assert "section text with facts" not in prompt
        assert search_call["model"] == "ollama/m1"
        assert search_call["temperature"] == 0
        # answer call gets the selected node's text as context
        answer_prompt = scripted_llm.calls[1]["messages"][0]["content"]
        assert "overview section text with facts" in answer_prompt

    def test_unknown_node_ids_ignored_gracefully(
        self,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
        tmp_path: Path,
        patched_md_to_tree: list[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import litellm

        scripted = ScriptedLiteLLM(
            [json.dumps({"node_list": ["9999"]}), "best-effort answer"]
        )
        monkeypatch.setattr(litellm, "completion", scripted.completion)
        strategy = PageIndexOfficialStrategy(cache_dir=tmp_path)
        strategy.prepare(mini_corpus, "m1")
        answer = strategy.answer(mini_dataset.get("q001"), "m1")
        assert answer.retrieved_ids == []
        assert answer.text == "best-effort answer"

    def test_fenced_json_response_parsed(
        self,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
        tmp_path: Path,
        patched_md_to_tree: list[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import litellm

        fenced = '```json\n{"node_list": ["0001"]}\n```'
        scripted = ScriptedLiteLLM([fenced, "answer text"])
        monkeypatch.setattr(litellm, "completion", scripted.completion)
        strategy = PageIndexOfficialStrategy(cache_dir=tmp_path)
        strategy.prepare(mini_corpus, "m1")
        answer = strategy.answer(mini_dataset.get("q001"), "m1")
        assert answer.retrieved_ids == ["docs/api.md"]

    def test_metadata(self) -> None:
        assert PageIndexOfficialStrategy.name == "pageindex_official"
        assert PageIndexOfficialStrategy.representation == "docs"
