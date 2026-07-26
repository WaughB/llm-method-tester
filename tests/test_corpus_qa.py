"""Tests for the gold Q&A dataset loader."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from llm_bench.corpus.qa import QADataset


class TestQADataset:
    def test_loads_questions(self, mini_corpus_root: Path) -> None:
        ds = QADataset.load(mini_corpus_root / "qa" / "questions.json")
        assert len(ds) == 3
        q = ds.get("q002")
        assert q.category == "multi_hop"
        assert q.expected_keywords == [["10 requests", "10 per minute"], ["gizmo", "/gizmo"]]
        assert q.source_notes[0] == "vault/Reference/Rate Limits.md"

    def test_iteration_preserves_order(self, mini_corpus_root: Path) -> None:
        ds = QADataset.load(mini_corpus_root / "qa" / "questions.json")
        assert [q.id for q in ds] == ["q001", "q002", "q003"]

    def test_invalid_category_rejected(self, tmp_path: Path) -> None:
        bad = [
            {
                "id": "q1",
                "question": "?",
                "category": "not_a_category",
                "expected_keywords": [["x"]],
                "source_docs": [],
                "source_notes": [],
                "gold_answer": "x",
            }
        ]
        path = tmp_path / "questions.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValidationError):
            QADataset.load(path)

    def test_duplicate_ids_rejected(self, tmp_path: Path) -> None:
        q = {
            "id": "q1",
            "question": "?",
            "category": "single_hop",
            "expected_keywords": [["x"]],
            "source_docs": [],
            "source_notes": [],
            "gold_answer": "x",
        }
        path = tmp_path / "questions.json"
        path.write_text(json.dumps([q, q]), encoding="utf-8")
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            QADataset.load(path)
