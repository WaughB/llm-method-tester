"""PageIndex precision-stage tests on fakes."""

import json
from pathlib import Path

import pytest
from llm_bench.llm.fake import FakeLLMClient

from pageindex_test.obs.trace import TraceRecorder
from pageindex_test.retrieval.fusion import FusedHit
from pageindex_test.retrieval.trees import TreeStage, TreeStageOverBudget

DOC_MD = """# Ops Guide

Intro paragraph.

## Restarting

Run restart-now to bounce the coordinator.

## Monitoring

Metrics on port 9137.
"""


@pytest.fixture
def library(tmp_path: Path) -> Path:
    (tmp_path / "trees").mkdir()
    doc_dir = tmp_path / "docs" / "doc-1"
    doc_dir.mkdir(parents=True)
    (doc_dir / "extracted.md").write_text(DOC_MD, encoding="utf-8")
    return tmp_path


def make_stage(library: Path, llm: FakeLLMClient, **kwargs) -> TreeStage:
    return TreeStage(
        llm=llm,
        tree_cache_dir_resolver=lambda loc: library / "trees",
        extracted_path_resolver=lambda loc, doc_id: library / "docs" / doc_id / "extracted.md",
        doc_title_resolver=lambda doc_id: "Ops Guide",
        **kwargs,
    )


def fused_for(doc_id: str) -> list[FusedHit]:
    return [
        FusedHit(chunk_id=f"{doc_id}#0", doc_id=doc_id, score=1.0, in_lexical=True, in_vector=True)
    ]


class TestTreeBuildCache:
    def test_builds_and_caches_forest(self, library: Path) -> None:
        stage = make_stage(library, FakeLLMClient())
        forest = stage.get_or_build_forest("loc", "doc-1")
        assert forest[0].title == "Ops Guide"
        assert [c.title for c in forest[0].children] == ["Restarting", "Monitoring"]
        cached = list((library / "trees").glob("doc-1_*.json"))
        assert len(cached) == 1
        # second call hits the cache (same content hash)
        again = stage.get_or_build_forest("loc", "doc-1")
        assert [c.title for c in again[0].children] == ["Restarting", "Monitoring"]

    def test_cache_invalidates_on_content_change(self, library: Path) -> None:
        stage = make_stage(library, FakeLLMClient())
        stage.get_or_build_forest("loc", "doc-1")
        (library / "docs" / "doc-1" / "extracted.md").write_text(
            "# Ops Guide\n\n## Changed\n\nnew", encoding="utf-8"
        )
        forest = stage.get_or_build_forest("loc", "doc-1")
        assert [c.title for c in forest[0].children] == ["Changed"]
        assert len(list((library / "trees").glob("doc-1_*.json"))) == 2

    def test_missing_extracted_returns_empty(self, library: Path) -> None:
        stage = make_stage(library, FakeLLMClient())
        assert stage.get_or_build_forest("loc", "ghost") == []


class TestRun:
    def test_selects_sections_and_cites_them(self, library: Path) -> None:
        llm = FakeLLMClient(
            responses={
                "navigating tables of contents": json.dumps(
                    {"node_ids": ["n0002"], "reasoning": "restart section"}
                )
            }
        )
        stage = make_stage(library, llm)
        recorder = TraceRecorder()
        result = stage.run(recorder, "loc", "How do I restart?", "m", fused_for("doc-1"))
        assert "restart-now" in result.context
        assert "Metrics on port" not in result.context  # sibling excluded
        assert result.citations[0].heading == "Restarting"
        assert result.citations[0].doc_id == "doc-1"
        assert result.llm_calls == 1
        stage_names = [s["name"] for s in recorder.stages_json()]
        assert stage_names == ["tree_build", "tree_select"]

    def test_no_valid_selection_raises_for_fallback(self, library: Path) -> None:
        llm = FakeLLMClient(default="not json at all")
        stage = make_stage(library, llm)
        with pytest.raises(TreeStageOverBudget, match="no usable sections"):
            stage.run(TraceRecorder(), "loc", "q", "m", fused_for("doc-1"))

    def test_over_budget_outline_raises(self, library: Path) -> None:
        big = "# Big\n\n" + "\n\n".join(f"## Section {i}\n\n{'word ' * 40}" for i in range(400))
        doc_dir = library / "docs" / "doc-big"
        doc_dir.mkdir(parents=True)
        (doc_dir / "extracted.md").write_text(big, encoding="utf-8")
        stage = make_stage(library, FakeLLMClient(), num_ctx=2048)
        with pytest.raises(TreeStageOverBudget, match="exceeds"):
            stage.run(TraceRecorder(), "loc", "q", "m", fused_for("doc-big"))

    def test_no_trees_raises(self, library: Path) -> None:
        stage = make_stage(library, FakeLLMClient())
        with pytest.raises(TreeStageOverBudget, match="No trees"):
            stage.run(TraceRecorder(), "loc", "q", "m", fused_for("ghost"))
