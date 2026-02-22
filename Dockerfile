FROM node:20-bookworm-slim AS web-build

WORKDIR /work/web

COPY web/package*.json ./

RUN if [ ! -s package.json ]; then echo '{}' > package.json; fi
RUN npm install --no-audit --no-fund

COPY web/ ./

RUN if [ ! -s package.json ]; then echo '{}' > package.json; fi
RUN mkdir -p dist && \
    if node -e "const fs=require('fs'); const pkg=JSON.parse((fs.readFileSync('package.json','utf8')||'{}')); process.exit(pkg.scripts && pkg.scripts.build ? 0 : 1);" && npm run build; then \
      echo 'web build completed'; \
    else \
      printf '%s\n' '<!doctype html><html><head><meta charset=\"utf-8\"><title>RAGPoison</title></head><body><div id=\"root\"></div></body></html>' > dist/index.html; \
    fi

FROM ghcr.io/astral-sh/uv:debian AS uv-binary

FROM python:3.12-slim AS app-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /workspace

COPY --from=uv-binary /usr/local/bin/uv /usr/local/bin/uv

RUN python -m venv /opt/venv

COPY api/pyproject.toml api/uv.lock /workspace/api/

RUN uv sync --project /workspace/api --frozen --no-install-project

COPY api/app /workspace/api/app
COPY --from=web-build /work/web/dist/ /workspace/api/app/static/

RUN mkdir -p /workspace/ml-100 /workspace/data

EXPOSE 8000

CMD ["sh", "-lc", "/opt/venv/bin/python -c \"import sys; sys.exit('Python >= 3.12 is required' if sys.version_info < (3, 12) else 0)\" && exec /opt/venv/bin/uvicorn api.app.main:app --host 0.0.0.0 --port 8000"]
