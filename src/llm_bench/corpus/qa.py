"""Gold-standard Q&A dataset schema and loader."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["single_hop", "multi_hop", "aggregation"]


class Question(BaseModel):
    id: str
    question: str
    category: Category
    # Alias groups: a group counts as "hit" if ANY alias appears in the answer.
    expected_keywords: list[list[str]] = Field(min_length=1)
    source_docs: list[str]
    source_notes: list[str]
    gold_answer: str


class QADataset:
    def __init__(self, questions: list[Question]) -> None:
        ids = [q.id for q in questions]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate question ids in dataset: {ids}")
        self._questions = questions
        self._by_id = {q.id: q for q in questions}

    @classmethod
    def load(cls, path: Path) -> "QADataset":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls([Question.model_validate(item) for item in raw])

    def get(self, question_id: str) -> Question:
        return self._by_id[question_id]

    def __iter__(self) -> Iterator[Question]:
        return iter(self._questions)

    def __len__(self) -> int:
        return len(self._questions)
