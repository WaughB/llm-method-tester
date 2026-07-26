"""CLI entrypoints: serve the API, run the worker, initialize the database."""

import typer
import uvicorn

from pageindex_test.config import Settings

app = typer.Typer(no_args_is_help=True, help="pageindex-test: staged retrieval prototype.")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8100, help="Bind port"),
) -> None:
    """Serve the API and frontend."""
    from pageindex_test.main import build_deps, create_app

    uvicorn.run(create_app(build_deps()), host=host, port=port)


@app.command()
def worker() -> None:
    """Run the job worker loop."""
    from pageindex_test.db.schema import init_schema, make_engine
    from pageindex_test.obs.jsonlog import configure_logging
    from pageindex_test.worker import run_forever

    settings = Settings()
    engine = make_engine(settings.database_url)
    init_schema(engine)
    configure_logging(engine)
    run_forever(engine)


@app.command("init-db")
def init_db() -> None:
    """Create all tables (idempotent)."""
    from pageindex_test.db.schema import init_schema, make_engine

    engine = make_engine(Settings().database_url)
    init_schema(engine)
    typer.echo("Schema initialized.")


if __name__ == "__main__":
    app()
