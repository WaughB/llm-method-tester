"""Tests for the CLI commands and the composition root."""

import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from llm_bench import wiring
from llm_bench.cli import app
from llm_bench.config import Settings

runner = CliRunner()


class TestCheckOllama:
    def test_reports_models_when_up(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/tags"
            return httpx.Response(
                200, json={"models": [{"name": "llama3.1:8b"}, {"name": "gpt-oss:20b"}]}
            )

        result = wiring.check_ollama("http://t", transport=httpx.MockTransport(handler))
        assert result == {"ok": True, "models": ["gpt-oss:20b", "llama3.1:8b"]}

    def test_reports_down(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        result = wiring.check_ollama("http://t", transport=httpx.MockTransport(handler))
        assert result["ok"] is False
        assert "refused" in result["error"]


class TestWiring:
    def test_build_runner_assembles_all_four_strategies(self, tmp_path: Path) -> None:
        settings = Settings(_env_file=None, cache_dir=tmp_path)
        repo = wiring.build_repo(settings)
        corpus = wiring.build_corpus(settings)
        dataset = wiring.build_dataset(settings)
        bench_runner = wiring.build_runner(settings, repo, corpus, dataset)
        assert bench_runner.available_strategies == [
            "baseline",
            "traditional_rag",
            "obsidian_rag",
            "pageindex",
            "pageindex_official",
        ]
        repo.close()


class TestCliCommands:
    def test_generate_corpus_to_custom_dir(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["generate-corpus", "--out", str(tmp_path / "c")])
        assert result.exit_code == 0
        assert (tmp_path / "c" / "qa" / "questions.json").exists()

    def test_validate_corpus_passes_on_committed_corpus(self) -> None:
        result = runner.invoke(app, ["validate-corpus"])
        assert result.exit_code == 0
        assert "All wikilinks resolve." in result.output
        assert "docs=13" in result.output

    def test_run_command_uses_wiring_and_prints_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # point cache/db at tmp and fake the LLM layer via a stub runner
        from llm_bench.corpus import BenchmarkCorpus
        from llm_bench.eval.evaluator import Evaluator
        from llm_bench.eval.judge import LLMJudge
        from llm_bench.llm.fake import FakeLLMClient
        from llm_bench.runner import BenchmarkRunner
        from llm_bench.strategies.baseline import BaselineStrategy

        def fake_build_runner(settings, repo, corpus: BenchmarkCorpus, dataset):
            fake = FakeLLMClient(
                default=json.dumps({"score": 1, "verdict": "incorrect", "reasoning": "n/a"})
            )
            return BenchmarkRunner(
                repo=repo,
                corpus=corpus,
                dataset=dataset,
                strategies=[BaselineStrategy(client=fake)],
                evaluator=Evaluator(judge=LLMJudge(client=fake, model="j")),
            )

        monkeypatch.setenv("LLM_BENCH_CACHE_DIR", str(tmp_path))
        monkeypatch.setattr(wiring, "build_runner", fake_build_runner)
        result = runner.invoke(app, ["run", "-m", "fake-model", "-q", "sh-01", "-q", "sh-02"])
        assert result.exit_code == 0
        assert "finished" in result.output
        assert "baseline" in result.output

    def test_help_lists_commands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for command in ("run", "serve", "generate-corpus", "validate-corpus"):
            assert command in result.output
