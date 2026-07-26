"""Lenient JSON extraction from LLM output.

Local models wrap JSON in prose or code fences, and Ollama's grammar-based
`format` enforcement returns empty responses on reasoning models (gpt-oss,
nemotron) — so we instruct JSON in the prompt and parse forgivingly instead.
"""

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict | None:
    """Best-effort: parse the whole text, any fenced block, or the first
    balanced {...} object. Returns None when nothing parses to a dict."""
    for candidate in _candidates(text):
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _candidates(text: str):
    yield text.strip()
    for match in _FENCE_RE.finditer(text):
        yield match.group(1).strip()
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    yield text[start : i + 1]
                    return
