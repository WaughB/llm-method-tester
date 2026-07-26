# llm-method-tester

**Benchmark how much retrieval strategy actually matters for local LLMs.**

[![CI](https://github.com/WaughB/llm-method-tester/actions/workflows/ci.yml/badge.svg)](https://github.com/WaughB/llm-method-tester/actions/workflows/ci.yml)
![Coverage](https://img.shields.io/badge/backend_coverage-%E2%89%A597%25-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

Four ways of answering questions over a document corpus, three free open-source models, one
gold-standard dataset — every cell measured for answer quality, retrieval accuracy, latency, and
LLM-call cost, with results in a live dashboard.

> **Dashboard:** `uv run llm-bench serve` → <http://localhost:8000> — comparison charts, a
> model×strategy heatmap, live run progress, and per-question drill-down with side-by-side
> answers from every model and strategy.

## The experiment

| | |
|---|---|
| **Models** | `gpt-oss:20b` · `nemotron-3-nano:4b` · `llama3.1:8b` (via [Ollama](https://ollama.com)) |
| **Strategies** | Baseline (no retrieval) · Traditional vector RAG · Obsidian-style RAG · PageIndex |
| **Corpus** | *Aurora Mesh* — a fictional distributed-config system: 13 technical docs + a 25-note Obsidian vault carrying the same facts |
| **Questions** | 30 gold-standard Q&As: single-hop, multi-hop, aggregation |
| **Metrics** | LLM-judge score (blind, 0–5) · keyword recall · retrieval hit rate · latency · tokens/sec · LLM calls per question |

**Why a fictional corpus?** Because no model can answer Aurora Mesh questions from pretraining,
the no-retrieval Baseline is a true control: every point a strategy scores above it is
attributable to retrieval, not memorization.

### The four strategies

1. **Baseline** — the model answers from its own knowledge. The control condition.
2. **Traditional RAG** — heading-aware chunking (~400 words, 50 overlap) → `nomic-embed-text`
   embeddings → [ChromaDB](https://www.trychroma.com/) cosine top-5 → context-stuffed prompt.
3. **Obsidian RAG** — retrieval that exploits vault *structure*: BM25 over weighted
   title/tags/body picks seed notes, then the strategy walks wikilinks **and backlinks** one hop
   out (score decay 0.5, shared-tag boost) — mimicking how a human hops through their vault.
   Retrieval is fully deterministic; the LLM only generates.
4. **PageIndex (reimpl)** — a faithful reimplementation of the vectorless, reasoning-based
   retrieval method from [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) (MIT):
   documents become TOC-like heading trees with LLM-written node summaries; at question time
   the model *reasons* over the tree outline to select sections, then descends one level to
   refine. Costs 2–3 LLM calls per question — and that cost is part of what the benchmark
   measures.
5. **PageIndex (official)** — the authors' **actual code**, vendored verbatim at commit
   [`190f8b3`](https://github.com/VectifyAI/PageIndex/tree/190f8b378be58199ca993566a9214dba72089c54)
   into [src/llm_bench/_vendor/pageindex](src/llm_bench/_vendor/pageindex): their `md_to_tree`
   builds the indexes and their published cookbook retrieval flow
   (`pageindex_RAG_simple.ipynb` — their search prompt, their JSON parsing, their answer
   prompt) answers questions, all through LiteLLM→Ollama as their code supports. Two disclosed
   adaptations for a multi-document benchmark: node ids are renumbered to stay unique across
   documents (same 4-digit format), and the search prompt receives a JSON list of per-document
   trees instead of a single tree. Having both variants means the reimplementation is
   *validated against* the official code on identical inputs.

## Results

From the reference run — full 3 × 4 × 30 matrix on an RTX 3080 (10GB), zero errors across
360 cells. Judge = blind LLM judge, 0–5. Recall = expected-fact keyword recall. Hit = share of
gold sources present in what the strategy retrieved. Latency = mean seconds per question
(includes all retrieval + generation calls).

| Model | Strategy | Judge | Recall | Hit rate | Latency | LLM calls |
|---|---|---:|---:|---:|---:|---:|
| gpt-oss:20b | Baseline | 0.30 | 3% | — | 39.1s | 1 |
| gpt-oss:20b | Vector RAG | 4.60 | 78% | 88% | 4.4s | 1 |
| gpt-oss:20b | Obsidian RAG | 4.60 | 75% | 82% | 4.5s | 1 |
| gpt-oss:20b | **PageIndex (reimpl)** | **5.00** | 82% | 83% | 38.4s | 3 |
| gpt-oss:20b | PageIndex (official) | 4.83 | 82% | **95%** | 33.5s | 2 |
| llama3.1:8b | Baseline | 0.20 | 3% | — | 48.0s | 1 |
| llama3.1:8b | Vector RAG | 4.53 | 83% | 88% | 0.8s | 1 |
| llama3.1:8b | Obsidian RAG | 4.47 | 87% | 82% | 2.7s | 1 |
| llama3.1:8b | PageIndex (reimpl) | 4.53 | 88% | 78% | 3.8s | 3 |
| llama3.1:8b | **PageIndex (official)** | **4.80** | 89% | 70% | 6.5s | 2 |
| nemotron-3-nano:4b | Baseline | 0.20 | 4% | — | 3.2s | 1 |
| nemotron-3-nano:4b | Vector RAG | 4.60 | 76% | 88% | 1.3s | 1 |
| nemotron-3-nano:4b | Obsidian RAG | 4.60 | 72% | 82% | 1.1s | 1 |
| nemotron-3-nano:4b | **PageIndex (reimpl)** | **4.70** | 77% | 73% | 6.9s | 3 |
| nemotron-3-nano:4b | PageIndex (official) | 3.37 | 56% | 55% | 6.5s | 2 |

**What the numbers say:**

- **The control worked.** Baselines score 0.2–0.3/5 with 3–4% fact recall — the fictional
  corpus really is unanswerable from pretraining, so everything above that is retrieval.
- **Retrieval is a ~20× quality lift** for every model, including the 4B nemotron — corpus
  access matters far more than parameter count on this task (a 4B model with RAG crushes a
  20B model without it).
- **PageIndex wins on answer quality on all three models** (a perfect 5.00 on gpt-oss), but
  pays for it: 2–3 LLM calls per question and up to ~9× the latency of vector RAG on the same
  model. Reasoning-based retrieval is a quality/cost trade, not a free win.
- **The official PageIndex code and the reimplementation agree on capable models** — within
  0.2–0.3 judge points on gpt-oss and llama, mutually validating both. On the 4B nemotron the
  official single-pass tree selection degrades (3.37 vs 4.70): choosing among all 174 nodes in
  one shot is harder for a small model than the reimplementation's two-stage capped-outline
  descent. Method structure matters more as models shrink.
- The full-tree prompt is also a context-window hazard: on nemotron's tokenizer the
  pretty-printed tree exceeded 16k tokens and Ollama silently truncated the question away
  (compact serialization fixed it — see the strategy docstring). Vectorless retrieval's
  scaling limit is the context window, and it fails silently when hit.
- **Vector RAG has the best retrieval hit rate (88%) and the best speed**, making it the
  efficiency sweet spot; Obsidian RAG's graph traversal lands close behind on entirely
  deterministic, embedding-free retrieval.
- Judge scores and keyword recall agree on the ranking — a useful sanity check on the blind
  LLM judge.

Full per-question data (answers, retrieved sources, judge reasoning) is in
[results/reference-run.json](results/reference-run.json) and explorable in the dashboard's
drill-down view.

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 18.18+, [Ollama](https://ollama.com) ≥ 0.32.

```bash
git clone https://github.com/WaughB/llm-method-tester
cd llm-method-tester
uv sync
ollama pull gpt-oss:20b && ollama pull llama3.1:8b && ollama pull nemotron-3-nano:4b && ollama pull nomic-embed-text
```

Run the full benchmark matrix (3 models × 4 strategies × 30 questions, then a judging pass):

```bash
uv run llm-bench run
```

Build the dashboard once, then serve everything from one process:

```bash
cd frontend && npm ci && npm run build && cd ..
uv run llm-bench serve
```

Open <http://localhost:8000>. From the dashboard you can launch runs, watch live progress, and
drill into any question to compare all twelve model×strategy answers side by side against the
gold answer.

### Docker

The whole stack (Ollama + app) also runs under Docker Compose:

```bash
docker compose up -d --build
docker compose exec ollama ollama pull gpt-oss:20b
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull nemotron-3-nano:4b
docker compose exec ollama ollama pull nomic-embed-text
```

Both services use `restart: unless-stopped`, so after a power outage or host reboot they come
back up on their own as soon as Docker starts. Results and index caches persist in the
`app-data` volume; models persist in `ollama-models` (or bind-mount an existing host model
directory — see the comment in [docker-compose.yml](docker-compose.yml)). GPU passthrough is
preconfigured for NVIDIA (requires the NVIDIA container toolkit; on Windows use Docker Desktop's
WSL2 backend) — delete the `deploy:` block to run CPU-only. Benchmarks can be launched from the
dashboard, or from the CLI inside the container:

```bash
docker compose exec app uv run llm-bench run
```

### CLI

```text
uv run llm-bench run                 # full matrix + judge pass
uv run llm-bench run -m llama3.1:8b -s pageindex -q sh-01   # any subset
uv run llm-bench run --resume 3      # crash-safe: finished cells are skipped
uv run llm-bench serve               # API + dashboard on :8000
uv run llm-bench validate-corpus     # corpus integrity check
uv run llm-bench generate-corpus     # regenerate the corpus deterministically
```

## Architecture

```mermaid
flowchart LR
    subgraph corpus["corpus/ (committed, generated)"]
        docs["docs/ 13 markdown files"]
        vault["vault/ 25 linked notes"]
        qa["qa/questions.json 30 gold Q&As"]
    end

    subgraph strategies["RetrievalStrategy implementations"]
        B["Baseline"]
        T["Traditional RAG chunk → embed → Chroma"]
        O["Obsidian RAG BM25 → link graph"]
        P["PageIndex heading tree → LLM traversal"]
    end

    R["BenchmarkRunner model-major matrix, resume, deferred judge pass"]
    E["Evaluator keyword recall · hit rate + blind LLM judge"]
    S[("SQLite runs / results")]
    A["FastAPI /api/*"]
    F["React dashboard"]
    OL["Ollama gpt-oss · nemotron · llama3.1 · nomic-embed"]

    corpus --> strategies
    strategies --> R --> E --> S --> A --> F
    strategies -.->|LLMClient / EmbeddingClient| OL
    E -.->|judge| OL
```

Every LLM/embedding access goes through injectable `LLMClient` / `EmbeddingClient` ABCs
([src/llm_bench/llm/base.py](src/llm_bench/llm/base.py)) — the whole test suite and CI run on
deterministic fakes, no GPU or Ollama required.

Design decisions worth knowing:

- **Model-major matrix order** — the runner iterates model → strategy → question so the GPU
  swaps models three times per run instead of hundreds.
- **Deferred judging** — the judge model (`gpt-oss:20b`) grades *after* the whole matrix
  finishes, in one batch, for the same reason. The judge is blind: it sees question, gold
  answer, expected facts, and candidate — never which model or strategy answered.
- **Crash-resumable runs** — every cell writes to SQLite immediately; per-cell failures land in
  the row's `error` column instead of killing the run; `--resume` skips finished cells.
- **Fair hit-rate scoring** — each strategy declares which corpus representation it retrieves
  from (`docs`, `vault`, or none), and is scored against that representation's gold sources.
- **Index caching** — Chroma collections and PageIndex summaries are keyed by corpus hash (and
  model, for summaries), so repeat runs skip index building.

## Repository layout

```text
corpus/                 # committed benchmark corpus (regenerate: llm-bench generate-corpus)
src/llm_bench/
  llm/                  # LLMClient/EmbeddingClient ABCs, Ollama impl, test fakes
  corpus/               # doc loader, Obsidian vault parser + link graph, QA schema
  strategies/           # baseline, traditional_rag, obsidian_rag, pageindex
  eval/                 # metrics, blind judge, evaluator
  storage/              # SQLite repository
  runner.py             # matrix orchestration
  api/ + cli.py         # FastAPI app + typer CLI
frontend/               # React 18 + Vite + Tailwind dashboard (vitest + msw)
tests/                  # 150+ tests, all on fakes — no GPU needed
```

## Development

Backend (Python 3.12, [uv](https://docs.astral.sh/uv/)):

```bash
uv run pytest            # 80% coverage gate enforced
uv run ruff check .
uv run pytest -m live    # optional smoke tests against a running Ollama
```

Frontend:

```bash
cd frontend
npm run dev              # Vite dev server, proxies /api to :8000
npm test                 # vitest + Testing Library + msw
npm run lint && npm run typecheck
```

CI runs lint, type checks, and both test suites (backend on Ubuntu **and** Windows) on every
push; the backend enforces ≥80% coverage (currently ~97%).

### Windows notes

- Store models on a big drive: set `OLLAMA_MODELS` (e.g. `D:\ollama-models`) as a *user*
  environment variable and fully restart Ollama. If Ollama later reports "model not found"
  for models you have, the server was restarted without the env var and fell back to `C:`.
- Runtime artifacts (results DB, index caches) default to `%LOCALAPPDATA%\llm-method-tester`,
  not the repo — OneDrive sync locks SQLite files mid-write. Override with `LLM_BENCH_CACHE_DIR`.

## Configuration

All settings are env-overridable with the `LLM_BENCH_` prefix (or a `.env` file):

| Variable | Default | |
|---|---|---|
| `LLM_BENCH_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `LLM_BENCH_MODELS` | the three benchmark models | JSON list |
| `LLM_BENCH_JUDGE_MODEL` | `gpt-oss:20b` | blind judge |
| `LLM_BENCH_EMBEDDING_MODEL` | `nomic-embed-text` | vector RAG embeddings |
| `LLM_BENCH_CACHE_DIR` | `%LOCALAPPDATA%\llm-method-tester` | DB + index caches |
| `LLM_BENCH_CORPUS_DIR` | `corpus` | benchmark corpus root |

## Acknowledgements

- **[PageIndex](https://github.com/VectifyAI/PageIndex)** by VectifyAI (MIT) — the vectorless
  reasoning-retrieval method. Their code is vendored verbatim as the `pageindex_official`
  strategy (see [PROVENANCE](src/llm_bench/_vendor/pageindex/PROVENANCE.md)) and independently
  reimplemented as the `pageindex` strategy.
- **[Ollama](https://ollama.com)** for making local models this easy.
- gpt-oss (OpenAI), Nemotron (NVIDIA), and Llama (Meta) — the open-weight models under test.

## License

MIT
