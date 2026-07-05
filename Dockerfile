# Production image: React UI + FastAPI, data from GCS at startup.
# No Playwright or repo secrets.json — auth is JWT/Garth tokens downloaded from GCS only.
FROM node:20-bookworm-slim AS ui
WORKDIR /ui
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

FROM python:3.11-slim AS app
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    GOLF_LIBRARY_DB=/data/library.db \
    GOLF_GARMIN_JSON=/data/golf-export.json \
    GOLF_DASHBOARD_SETTINGS=/data/dashboard_settings.json \
    GOLF_ON_COURSE_PLAYBOOK=/data/on_course_playbook.json \
    GOLF_ACCESS_TOKENS_FILE=/data/access_tokens.json \
    GOLF_DRILL_SESSIONS=/data/drill_sessions.json \
    GOLF_TRAINING_BLOCK=/data/training_block.json \
    GOLF_DASHBOARD_SECRETS=/data/dashboard_secrets.json \
    GOLF_RAPSODO_CONFIG=/app/config/rapsodo-endpoints.json \
    GOLF_DASHBOARD_DIST=/app/dashboard/dist \
    GOLF_DATA_DIR=/data \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY golf_analysis ./golf_analysis
COPY config/rapsodo-endpoints.example.json ./config/rapsodo-endpoints.json
COPY scripts/cloud_download_data.py ./scripts/cloud_download_data.py
RUN pip install --no-cache-dir . 'google-cloud-storage>=2.14' 'garth-ng[cli]>=1.1.0' 'httpx>=0.27' 'python-multipart>=0.0.9'

COPY --from=ui /ui/dist ./dashboard/dist
RUN mkdir -p /data

EXPOSE 8080
CMD ["sh", "-c", "python scripts/cloud_download_data.py && exec uvicorn golf_analysis.api.main:app --host 0.0.0.0 --port ${PORT}"]
