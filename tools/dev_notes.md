# End-to-End Developer Runbook

## Prerequisites

- Python `>=3.12`
- `uv`
- Docker Engine and Docker Compose plugin
- Run all commands from repo root

## Secrets Setup

Create provider secret files under `./secrets/`:

- `chatgpt_api_key.txt`
- `claude_api_key.txt`
- `gemini_api_key.txt`
- `qwen_api_key.txt`

Each file must contain only the raw key string (no labels, no JSON).

```bash
mkdir -p secrets
printf '%s' 'YOUR_CHATGPT_KEY' > secrets/chatgpt_api_key.txt
printf '%s' 'YOUR_CLAUDE_KEY' > secrets/claude_api_key.txt
printf '%s' 'YOUR_GEMINI_KEY' > secrets/gemini_api_key.txt
printf '%s' 'YOUR_QWEN_KEY' > secrets/qwen_api_key.txt
```

## Start the Stack

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

## Run the Wizard

```bash
uv run python -m api.app.cli.cli wizard
```

## Index and Run Evaluation

Compose indexer path:

```bash
docker compose -f docker/docker-compose.yml --profile indexing run --rm indexer
```

CLI path (reproducible local flow):

```bash
uv run python -m api.app.cli.cli data prepare
uv run python -m api.app.cli.cli attack build-poisoned
uv run python -m api.app.cli.cli index both
uv run python -m api.app.cli.cli eval run --mode full --label <run_label>
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
- Ollama model missing:
  - Use the wizard (`uv run python -m api.app.cli.cli wizard`) and run the local model install/pull flow in the LLM configuration screens.
