RAGPoison is a reproducible MovieLens 100K research platform for studying RAG poisoning attacks against a recommender, with a FastAPI backend, React frontend, Elasticsearch retrieval, local/cloud LLM provider selection, and experiment workflows via CLI and web UI.

## Prerequisites

Placeholder: Python 3.12+, uv, Docker, and Docker Compose requirements will be documented in later tasks.

## Setup

Use a single repo-root virtual environment at `.venv` with `uv`, while keeping per-project lockfiles in `api/uv.lock` and `sdk/python/uv.lock`.

## Run

Data pipeline commands (Task 05):

- `uv run --project api --no-project python -m api.app.cli.cli data prepare`
- `uv run --project api --no-project python -m api.app.cli.cli data profiles`
- `uv run --project api --no-project python -m api.app.cli.cli data splits`
- `uv run --project api --no-project python -m api.app.cli.cli data export-es`

`data export-es` now writes both:

- `data/processed/es_bulk_movies.jsonl`
- `data/processed/es_bulk_poisoned_movies.jsonl`

## Attack Bulk Generation (Task 10)

Generate poisoned movies bulk JSONL from baseline movies bulk using `data/config/attack_config.json`:

- `uv run --project api --no-project python -m api.app.cli.cli attack build-poisoned`

Output path:

- `data/processed/es_bulk_poisoned_movies.jsonl`

## Elasticsearch Indexing (Task 06)

Run the one-shot indexer service:

- `docker compose -f docker/docker-compose.yml --profile indexing run --rm indexer`

Or run scripts manually inside a container that has `/workspace` mounts:

- `/workspace/docker/scripts/wait-for-es.sh`
- `/workspace/docker/scripts/index_baseline.sh`
- `/workspace/docker/scripts/index_poisoned.sh`

Expected indices visible in Kibana:

- `movies`
- `movies_poisoned`

## Wizard

Full workflow wizard (Task 11):

- `uv run python -m api.app.cli.cli wizard`

Wizard sections:

- Environment checks
- Configure LLMs
- Data pipeline
- Elasticsearch indexing
- Configure attack
- Run experiments
- Generate reports
- Utilities

## Non-interactive Task 11 Commands

Indexing:

- `uv run python -m api.app.cli.cli index baseline`
- `uv run python -m api.app.cli.cli index poisoned`
- `uv run python -m api.app.cli.cli index both`
- `uv run python -m api.app.cli.cli index stats`
- `uv run python -m api.app.cli.cli index reset --yes`

Evaluation:

- `uv run python -m api.app.cli.cli eval run --mode single --user-id 1 --label demo_single`
- `uv run python -m api.app.cli.cli eval run --mode batch --batch-size 100 --label demo_batch`
- `uv run python -m api.app.cli.cli eval run --mode full --label demo_full`

Reporting:

- `uv run python -m api.app.cli.cli report generate --label demo_full`
