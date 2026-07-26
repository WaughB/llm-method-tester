"""Tests for lenient JSON extraction."""

from llm_bench.llm.jsonutil import extract_json


class TestExtractJson:
    def test_clean_json(self) -> None:
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_json_in_code_fence(self) -> None:
        assert extract_json('Here you go:\n```json\n{"a": 1}\n```\nDone.') == {"a": 1}

    def test_json_in_bare_fence(self) -> None:
        assert extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_json_embedded_in_prose(self) -> None:
        text = 'Sure! The answer is {"node_ids": ["n0001"], "reasoning": "intro"} as requested.'
        assert extract_json(text) == {"node_ids": ["n0001"], "reasoning": "intro"}

    def test_nested_objects(self) -> None:
        text = 'prefix {"outer": {"inner": 2}} suffix'
        assert extract_json(text) == {"outer": {"inner": 2}}

    def test_no_json_returns_none(self) -> None:
        assert extract_json("I think the answer is pretty good!") is None

    def test_empty_string_returns_none(self) -> None:
        assert extract_json("") is None

    def test_non_dict_json_rejected(self) -> None:
        assert extract_json("[1, 2, 3]") is None

    def test_unbalanced_braces_returns_none(self) -> None:
        assert extract_json('{"a": ') is None
