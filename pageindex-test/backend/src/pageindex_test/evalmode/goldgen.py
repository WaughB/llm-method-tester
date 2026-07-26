"""LLM-assisted gold-question generation from ingested documents.

Generated questions land unapproved; the user reviews and approves them in
the Eval UI before they count. Parsing is lenient (extract_json) and each
question is validated against the documents it claims as gold sources.
"""

import logging

from llm_bench.llm.base import GenOptions, LLMClient
from llm_bench.llm.jsonutil import extract_json

logger = logging.getLogger("pageindex_test.evalmode")

_GEN_PROMPT = """You are creating a question-answering evaluation set from the \
user's documents. Below are excerpts from one document.

Document id: {doc_id}
Excerpts:
{excerpts}

Write {n} factual questions that can be answered ONLY from these excerpts.
For each question give 1-3 expected keyword groups: a group is a list of \
acceptable phrasings of one fact that a correct answer must contain \
(short, distinctive strings that literally appear in the excerpts).

Respond with ONLY this JSON:
{{"questions": [{{"question": "...",
  "expected_keywords": [["phrase", "alt-phrase"], ...]}}, ...]}}"""


def generate_questions(
    llm: LLMClient,
    model: str,
    doc_id: str,
    chunk_texts: list[str],
    *,
    per_doc: int = 3,
) -> list[dict]:
    excerpts = "\n\n".join(chunk_texts[:6])
    response = llm.generate(
        model,
        _GEN_PROMPT.format(doc_id=doc_id, excerpts=excerpts[:8000], n=per_doc),
        options=GenOptions(),
    )
    parsed = extract_json(response.text) or {}
    haystack = " ".join(chunk_texts).lower()
    questions = []
    for item in parsed.get("questions") or []:
        question = str(item.get("question", "")).strip()
        groups = [
            [str(alias) for alias in group if str(alias).strip()]
            for group in (item.get("expected_keywords") or [])
            if isinstance(group, list) and group
        ]
        # keep only keyword groups whose aliases actually appear in the source
        groups = [group for group in groups if any(alias.lower() in haystack for alias in group)]
        if question and groups:
            questions.append(
                {"question": question, "expected_keywords": groups, "gold_doc_ids": [doc_id]}
            )
    logger.info(
        "questions generated",
        extra={"data": {"doc_id": doc_id, "kept": len(questions)}},
    )
    return questions
