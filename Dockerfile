# Production image: React UI + FastAPI, data from GCS at startup.
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
    GOLF_DASHBOARD_DIST=/app/dashboard/dist \
    GOLF_DATA_DIR=/data \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY golf_analysis ./golf_analysis
COPY scripts/cloud_download_data.py ./scripts/cloud_download_data.py
RUN pip install --no-cache-dir . 'google-cloud-storage>=2.14'

COPY --from=ui /ui/dist ./dashboard/dist
RUN mkdir -p /data

EXPOSE 8080
CMD ["sh", "-c", "python scripts/cloud_download_data.py && exec uvicorn golf_analysis.api.main:app --host 0.0.0.0 --port ${PORT}"]
