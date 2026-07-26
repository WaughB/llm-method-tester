"""Tests for the PageIndex strategy with scripted fake LLM responses."""

import json
from pathlib import Path

import pytest

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import QADataset
from llm_bench.llm.fake import FakeLLMClient
from llm_bench.strategies.pageindex import PageIndexStrategy


def make_fake(selection: dict, refinement: dict | None = None) -> FakeLLMClient:
    """Fake that answers summaries, selection, refinement, and generation."""
    responses = {
        "Summarize this section": "A short summary.",
        "Select up to": json.dumps(selection),
        "final answer": "The answer from PageIndex context.",
    }
    if refinement is not None:
        responses["Refine your selection"] = json.dumps(refinement)
    return FakeLLMClient(responses=responses, default="The answer from PageIndex context.")


@pytest.fixture
def prepared(
    mini_corpus: BenchmarkCorpus, tmp_path: Path
) -> tuple[PageIndexStrategy, FakeLLMClient]:
    # ops.md root is n0005; its children: Restarting n0006, Monitoring n0007
    fake = make_fake(
        selection={"node_ids": ["n0005"], "reasoning": "ops doc"},
        refinement={"node_ids": ["n0006"], "reasoning": "restart section"},
    )
    strategy = PageIndexStrategy(llm=fake, cache_dir=tmp_path)
    strategy.prepare(mini_corpus, "model-a")
    return strategy, fake


class TestPageIndexStrategy:
    def test_metadata(self) -> None:
        assert PageIndexStrategy.name == "pageindex"
        assert PageIndexStrategy.representation == "docs"

    def test_prepare_summarizes_every_node_once_and_caches(
        self, mini_corpus: BenchmarkCorpus, tmp_path: Path
    ) -> None:
        fake = make_fake(selection={"node_ids": []})
        strategy = PageIndexStrategy(llm=fake, cache_dir=tmp_path)
        strategy.prepare(mini_corpus, "model-a")
        summary_calls = [c for c in fake.calls if "Summarize this section" in c.prompt]
        # mini corpus: 3 docs -> 3 roots + 7 sections/subsections = 10 nodes
        assert len(summary_calls) == 10
        # cache file written; a fresh instance re-uses it without new LLM calls
        fake2 = make_fake(selection={"node_ids": []})
        strategy2 = PageIndexStrategy(llm=fake2, cache_dir=tmp_path)
        strategy2.prepare(mini_corpus, "model-a")
        assert [c for c in fake2.calls if "Summarize" in c.prompt] == []

    def test_traversal_selects_then_refines_then_answers(
        self,
        prepared: tuple[PageIndexStrategy, FakeLLMClient],
        mini_dataset: QADataset,
    ) -> None:
        strategy, fake = prepared
        answer = strategy.answer(mini_dataset.get("q003"), "model-a")
        assert answer.text == "The answer from PageIndex context."
        # selection + refinement + generation
        assert answer.llm_calls == 3
        assert answer.retrieved_ids == ["docs/ops.md"]
        # refined node's text is in the final generation prompt
        generation_prompt = fake.calls[-1].prompt
        assert "widget restart" in generation_prompt
        # sibling section was refined away
        assert "Prometheus" not in generation_prompt

    def test_selection_without_children_skips_refinement(
        self, mini_corpus: BenchmarkCorpus, tmp_path: Path, mini_dataset: QADataset
    ) -> None:
        # n0006 (Restarting) is a leaf: no refinement round expected
        fake = make_fake(selection={"node_ids": ["n0006"]})
        strategy = PageIndexStrategy(llm=fake, cache_dir=tmp_path)
        strategy.prepare(mini_corpus, "model-a")
        answer = strategy.answer(mini_dataset.get("q003"), "model-a")
        assert answer.llm_calls == 2  # selection + generation only
        assert answer.retrieved_ids == ["docs/ops.md"]

    def test_unknown_node_ids_ignored(
        self, mini_corpus: BenchmarkCorpus, tmp_path: Path, mini_dataset: QADataset
    ) -> None:
        fake = make_fake(selection={"node_ids": ["n9999", "n0006"]})
        strategy = PageIndexStrategy(llm=fake, cache_dir=tmp_path)
        strategy.prepare(mini_corpus, "model-a")
        answer = strategy.answer(mini_dataset.get("q003"), "model-a")
        assert answer.retrieved_ids == ["docs/ops.md"]

    def test_malformed_selection_yields_empty_context_not_crash(
        self, mini_corpus: BenchmarkCorpus, tmp_path: Path, mini_dataset: QADataset
    ) -> None:
        fake = FakeLLMClient(
            responses={
                "Summarize this section": "A short summary.",
                "Select up to": "not json at all",
            },
            default="best-effort answer",
        )
        strategy = PageIndexStrategy(llm=fake, cache_dir=tmp_path)
        strategy.prepare(mini_corpus, "model-a")
        answer = strategy.answer(mini_dataset.get("q001"), "model-a")
        assert answer.text == "best-effort answer"
        assert answer.retrieved_ids == []

    def test_outline_contains_ids_titles_summaries(
        self,
        prepared: tuple[PageIndexStrategy, FakeLLMClient],
        mini_dataset: QADataset,
    ) -> None:
        strategy, fake = prepared
        strategy.answer(mini_dataset.get("q001"), "model-a")
        selection_prompt = next(c.prompt for c in fake.calls if "Select up to" in c.prompt)
        assert "[n0001]" in selection_prompt
        assert "Widget API" in selection_prompt
        assert "A short summary." in selection_prompt
