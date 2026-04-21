# End-to-End Developer Runbook

## Prerequisites

- Python `>=3.12`
- `uv`
- Docker Engine and Docker Compose plugin
- Run all commands from repo root

## Secrets Setup (Env-First)

Use `.env` as the primary credentials source:

```bash
cp .env.example .env
```

Set provider keys in `.env`:

- `CHATGPT_API_KEY`
- `CLAUDE_API_KEY`
- `GEMINI_API_KEY`
- `QWEN_API_KEY`

Optional shared transit config:

- `OPENAI_COMPAT_BASE_URL`
- `OPENAI_COMPAT_API_KEY`

Provider keys are read from repo-root `.env` / `.env.key`; `./secrets/` files are no longer used.

## Start the Stack

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

The `RagPoison` service explicitly loads repo-root `.env` first and `.env.key` second, so `.env.key` overrides `.env` when both define the same key.

## Run the Wizard

```bash
docker compose -f docker/docker-compose.yml exec RagPoison uv run --project api python -m api.app.cli.cli wizard
```

Optional host-run mode (dev, publish Elasticsearch first):

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d --build
ELASTICSEARCH_URL=http://localhost:9200 uv run --project api python -m api.app.cli.cli wizard
```

Refresh the curated cloud model snapshot from official provider APIs:

```bash
uv run --project api python -m api.app.cli.cli llm refresh-models
```

## Index and Run Evaluation

Compose indexer path:

```bash
docker compose -f docker/docker-compose.yml --profile indexing run --rm indexer
```

CLI path (reproducible local flow):

```bash
uv run --project api python -m api.app.cli.cli data prepare
uv run --project api python -m api.app.cli.cli attack build-poisoned
uv run --project api python -m api.app.cli.cli index both
uv run --project api python -m api.app.cli.cli eval run --mode full --label <run_label>
```

Evaluation artifacts are written under:

- `data/results/runs/<run_label>/...`

## Open Kibana and Find Indices

- Open Kibana: `http://localhost:5601`
- In Kibana, go to Dev Tools and run:

```http
GET _cat/indices/movies*?v
```

Expected indices:

- `movies`
- `movies_poisoned`

## Data Safety and down -v

- `./data` and `./ml-100` are bind mounts in compose:
  - `../data:/workspace/data`
  - `../ml-100:/workspace/ml-100`
- Because they are host bind mounts, those directories persist even after:
  - `docker compose -f docker/docker-compose.yml down -v`
- Named volumes `es_data` and `ollama_data` can be removed by `down -v`; they are rebuildable Elasticsearch/Ollama state and cache.

## Troubleshooting

- Elasticsearch memory:
  - Compose sets `ES_JAVA_OPTS=-Xms1g -Xmx1g`.
  - If Elasticsearch fails to start on low-memory hosts, lower both values consistently (for example `-Xms512m -Xmx512m`) and restart.
- Elasticsearch health:
  - `yellow` cluster health is acceptable for this single-node setup.
- Elasticsearch DNS context:
  - `elasticsearch` is a Docker Compose service hostname and resolves only inside compose containers.
  - Host-shell commands should use `http://localhost:9200` when Elasticsearch is published (for example via `docker/docker-compose.dev.yml`).
- Ollama model missing:
  - Use the wizard (`docker compose -f docker/docker-compose.yml exec RagPoison uv run --project api python -m api.app.cli.cli wizard`) and run the local model install/pull flow in the LLM configuration screens.
- Cloud model drift:
  - Run `uv run --project api python -m api.app.cli.cli llm refresh-models`.
  - Qwen catalog refresh uses Aliyun China DashScope as the source of truth.
