"""Composition root: builds real (Ollama-backed) object graphs from settings."""

from pathlib import Path

import chromadb
import httpx

from llm_bench.api.app import ApiDeps
from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import QADataset
from llm_bench.eval.evaluator import Evaluator
from llm_bench.eval.judge import LLMJudge
from llm_bench.llm.ollama import OllamaClient, OllamaEmbeddingClient
from llm_bench.runner import BenchmarkRunner
from llm_bench.storage.repository import ResultsRepository
from llm_bench.strategies.baseline import BaselineStrategy
from llm_bench.strategies.obsidian_rag import ObsidianRAGStrategy
from llm_bench.strategies.pageindex import PageIndexStrategy
from llm_bench.strategies.traditional_rag import TraditionalRAGStrategy
from llm_bench.config import Settings


def build_corpus(settings: Settings) -> BenchmarkCorpus:
    return BenchmarkCorpus.load(settings.corpus_dir)


def build_dataset(settings: Settings) -> QADataset:
    return QADataset.load(settings.corpus_dir / "qa" / "questions.json")


def build_repo(settings: Settings) -> ResultsRepository:
    return ResultsRepository(settings.db_path)


def build_runner(
    settings: Settings,
    repo: ResultsRepository,
    corpus: BenchmarkCorpus,
    dataset: QADataset,
) -> BenchmarkRunner:
    llm = OllamaClient(settings.ollama_base_url, timeout_s=settings.request_timeout_s)
    embedder = OllamaEmbeddingClient(settings.ollama_base_url, model=settings.embedding_model)
    chroma = chromadb.PersistentClient(path=str(settings.cache_dir / "chroma"))
    strategies = [
        BaselineStrategy(client=llm),
        TraditionalRAGStrategy(llm=llm, embedder=embedder, chroma_client=chroma),
        ObsidianRAGStrategy(llm=llm),
        PageIndexStrategy(llm=llm, cache_dir=settings.cache_dir),
    ]
    judge = LLMJudge(client=llm, model=settings.judge_model)
    return BenchmarkRunner(
        repo=repo,
        corpus=corpus,
        dataset=dataset,
        strategies=strategies,
        evaluator=Evaluator(judge=judge),
    )


def check_ollama(base_url: str, transport: httpx.BaseTransport | None = None) -> dict:
    """Health probe: is Ollama reachable and which models are pulled?"""
    try:
        with httpx.Client(base_url=base_url, timeout=5.0, transport=transport) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            models = sorted(m["name"] for m in response.json().get("models", []))
            return {"ok": True, "models": models}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return {"ok": False, "models": [], "error": str(exc)}


def build_api_deps(settings: Settings) -> ApiDeps:
    corpus = build_corpus(settings)
    dataset = build_dataset(settings)
    repo = build_repo(settings)
    runner = build_runner(settings, repo, corpus, dataset)
    frontend_dist = Path("frontend") / "dist"
    return ApiDeps(
        repo=repo,
        runner=runner,
        dataset=dataset,
        models=settings.models,
        health_check=lambda: check_ollama(settings.ollama_base_url),
        frontend_dist=frontend_dist if frontend_dist.exists() else None,
    )
