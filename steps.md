uv run --project api python -m api.app.cli.cli data prepare
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d --build
 sudo ELASTICSEARCH_URL=http://localhost:9200 uv run --project api python -m api.app.cli.cli index baseline
 sudo ELASTICSEARCH_URL=http://localhost:9200 uv run --project api python -m api.app.cli.cli attack build-poisoned
 sudo ELASTICSEARCH_URL=http://localhost:9200 uv run --project api python -m api.app.cli.cli index poisoned
 sudo ELASTICSEARCH_URL=http://localhost:9200 uv run --project api python -m api.app.cli.cli wizard               
uv sync --project api --frozen
uv sync --project sdk/python --frozen