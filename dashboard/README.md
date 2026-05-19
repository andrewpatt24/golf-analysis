# Golf dashboard (dev)

React + Vite + TypeScript + **Material UI (MUI)** + Recharts. UI follows [Material Design](https://m2.material.io/) patterns (typography, surfaces, components) via [MUI Material](https://mui.com/material-ui/), which is the standard React mapping for those guidelines.

## Visual system

## `npm: command not found`

The UI needs **Node.js** (which includes `npm`).

**macOS (Homebrew)**

```bash
brew install node
```

Close and reopen the terminal, then check:

```bash
node -v
npm -v
```

**macOS / Windows / Linux**

Install the **LTS** build from [https://nodejs.org](https://nodejs.org) and ensure your PATH includes the Node `bin` directory.

---

**No Node on the machine?** Use Docker (see below) so only Docker is required.

## Docker on an older Mac (e.g. macOS 12.7.x)

If you meant **macOS 12.7.6** (Monterey) on an older laptop, you need a **Docker runtime** first. The dashboard does not care about a “Docker 12.x” app version specifically—what matters is a working `docker` CLI and enough RAM (try **4 GB** reserved for Docker if the machine is tight).

### Option A — Docker Desktop (simplest)

1. Download **Docker Desktop for Mac** from [Docker’s release notes / archives](https://docs.docker.com/desktop/release-notes/) and pick a **4.x** build that still lists **macOS Monterey (12)** if the latest installer refuses to run.
2. Install, open Docker Desktop, wait until it says **Docker is running**.
3. In **Settings → Resources**, lower CPUs to **2** and Memory to **3–4 GB** if the laptop struggles.
4. Verify:

```bash
docker run --rm hello-world
```

### Option B — Colima (lighter than Desktop; good for old Macs)

If Docker Desktop is too heavy or won’t install:

```bash
brew install colima docker
colima start --cpu 2 --memory 4 --disk 20
docker run --rm hello-world
```

Use the same `docker` commands below once Colima is running.

### Run the dashboard UI in Docker

1. **Terminal 1 — API on the host** (from repo root):

```bash
cd /path/to/golf-analysis
uv sync
uv run golf-ingest --db data/library.db dashboard-api --reload
```

2. **Terminal 2 — UI in a Node container** (from repo root):

```bash
./dashboard/docker-dev.sh
```

That script bind-mounts `dashboard/`, runs `npm install` + Vite, and sets `VITE_PROXY_TARGET=http://host.docker.internal:8000` so the browser talks to the UI on `:5173`, while Vite proxies `/api` to your Mac’s FastAPI on port **8000**.

**Overrides** (optional):

```bash
API_PORT=8000 NODE_IMAGE=node:20-bookworm-slim ./dashboard/docker-dev.sh
# If host.docker.internal fails (very old Docker), use your LAN IP:
VITE_PROXY_TARGET=http://192.168.1.10:8000 ./dashboard/docker-dev.sh
```

**First `npm install` inside Docker** downloads packages; on a slow machine it can take several minutes. The `node:20-bookworm-slim` image keeps download size smaller than full `bookworm`.

### If you literally meant “Docker v12.7.6”

That is not a standard Docker Engine label. Check what you have:

```bash
docker version
```

You need a client that supports `docker run` with **volume mounts** and **port publishing** (Docker Engine **19.03+** is typical). If `docker version` fails or is extremely old, install current **Docker Desktop** or **Colima** as above.

## Run locally

**Important:** `package.json` is inside **`dashboard/`**. Run `npm install` and `npm run dev` from that directory (or use `npm --prefix dashboard`). Running `npm` in the **repo root** causes `ENOENT ... package.json`.

**Terminal 1 — API** (from repo root; uses `golf-ingest --db` path):

```bash
uv sync
uv run golf-ingest --db data/library.db dashboard-api --reload
```

Optional env:

- `GOLF_LIBRARY_DB` — SQLite path (CLI sets this from `--db`).
- `GOLF_GARMIN_JSON` — path to `golf-export.json` for last-10 SG on the Performance tab.
- `GOLF_CORS_ORIGINS` — comma-separated allowed origins (defaults include `http://localhost:5173`).
- `GOLF_DASHBOARD_DIST` — if set to a built `dist/` folder, the API can also serve static files (optional).

**Terminal 2 — UI** (from **`dashboard/`** — not the repo root):

```bash
cd /path/to/golf-analysis/dashboard
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:8000` by default.

### Proxy target (API not on localhost)

Set `VITE_PROXY_TARGET` before `npm run dev` if the API runs elsewhere, for example:

```bash
export VITE_PROXY_TARGET=http://host.docker.internal:8000
npm run dev
```

Then open `http://localhost:5173`.

**Equivalent one-liner** (same as the script; from repo root):

```bash
docker run --rm -it \
  -v "$(pwd)/dashboard:/app" -w /app \
  -p 5173:5173 \
  -e VITE_PROXY_TARGET=http://host.docker.internal:8000 \
  node:20-bookworm-slim \
  bash -lc "npm install && npx vite --host 0.0.0.0 --port 5173"
```

## Production-style

```bash
cd dashboard && npm run build
```

Point `GOLF_DASHBOARD_DIST` at `dashboard/dist` when starting uvicorn, or serve `dist/` with nginx and the API separately.

## Tabs

| Tab | Data source |
|-----|----------------|
| Strategy | Garmin JSON scorecards + ESZ/DSZ from `shotDetails`; configurable round-by-round line chart (dual axis for % vs counts). |
| Performance | Round summary from SQLite + Garmin JSON last-10 samples if file present. |
| Training | Rapsodo LM cohort from SQLite (year from Settings). |
| Plans | Training block + insights from API (NBLM-style templates + real flags). |
| Settings | `data/dashboard_settings.json` via API. |
