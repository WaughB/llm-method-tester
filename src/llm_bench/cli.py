"""Command-line interface: run benchmarks, serve the dashboard, manage the corpus."""

from pathlib import Path

import typer
import uvicorn

from llm_bench import wiring
from llm_bench.config import Settings
from llm_bench.corpus import BenchmarkCorpus
from llm_bench.runner import RunProgress

app = typer.Typer(no_args_is_help=True, help="Benchmark LLM retrieval strategies.")


@app.command()
def run(
    model: list[str] = typer.Option(None, "--model", "-m", help="Models (default: all three)"),
    strategy: list[str] = typer.Option(None, "--strategy", "-s", help="Strategies (default: all)"),
    question: list[str] = typer.Option(None, "--question", "-q", help="Question ids"),
    resume: int = typer.Option(None, "--resume", help="Resume an existing run id"),
) -> None:
    """Run the benchmark matrix against local Ollama models."""
    settings = Settings()
    repo = wiring.build_repo(settings)
    corpus = wiring.build_corpus(settings)
    dataset = wiring.build_dataset(settings)
    runner = wiring.build_runner(settings, repo, corpus, dataset)

    def report(progress: RunProgress) -> None:
        typer.echo(f"[{progress.done}/{progress.total}] {progress.current}")

    run_id = runner.run(
        models=list(model) if model else settings.models,
        strategy_names=list(strategy) if strategy else None,
        question_ids=list(question) if question else None,
        resume_run_id=resume,
        progress=report,
    )
    typer.echo(f"Run {run_id} finished.")
    for row in repo.summary_for_run(run_id):
        score = f"{row.avg_judge_score:.2f}" if row.avg_judge_score is not None else "-"
        recall = f"{row.avg_keyword_recall:.2f}" if row.avg_keyword_recall is not None else "-"
        typer.echo(
            f"  {row.model:<22} {row.strategy:<16} judge={score} recall={recall} "
            f"errors={row.error_count}/{row.count}"
        )


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
) -> None:
    """Serve the API and the built frontend dashboard."""
    uvicorn.run(_build_app(Settings()), host=host, port=port)


def _build_app(settings: Settings):
    from llm_bench.api.app import create_app

    return create_app(wiring.build_api_deps(settings))


@app.command("generate-corpus")
def generate_corpus(
    out: Path = typer.Option(None, "--out", help="Output directory (default: settings corpus dir)"),
) -> None:
    """Regenerate the Aurora Mesh benchmark corpus."""
    from llm_bench.corpus_gen import generate

    target = out or Settings().corpus_dir
    generate(target)
    typer.echo(f"Corpus written to {target}")


@app.command("validate-corpus")
def validate_corpus() -> None:
    """Check corpus integrity: sizes, wikilink resolution."""
    settings = Settings()
    corpus = BenchmarkCorpus.load(settings.corpus_dir)
    dataset = wiring.build_dataset(settings)
    typer.echo(f"docs={len(corpus.documents)} notes={len(corpus.vault)} questions={len(dataset)}")
    if corpus.vault.unresolved_links:
        for note_id, target in sorted(corpus.vault.unresolved_links):
            typer.echo(f"UNRESOLVED: {note_id} -> [[{target}]]")
        raise typer.Exit(code=1)
    typer.echo("All wikilinks resolve.")


if __name__ == "__main__":
    app()
