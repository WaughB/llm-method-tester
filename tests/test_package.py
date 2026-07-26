"""Smoke test: the package imports and exposes a version."""

import llm_bench


def test_package_has_version() -> None:
    assert isinstance(llm_bench.__version__, str)
    assert llm_bench.__version__.count(".") == 2
