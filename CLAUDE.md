# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (creates .venv)
uv sync

# Run the CLI
uv run tver-dl --config config.yaml

# Lint
uvx ruff check .
uvx ruff format .

# Run tests
uv run pytest

# Build wheel (used by CI release workflow)
python -m build
```

Docker:
```bash
docker compose up --build
```

The `SETUPTOOLS_SCM_PRETEND_VERSION` env var must be set in the Dockerfile because there is no git history in the Docker build context and the version is sourced from VCS via hatch-vcs.

## Architecture

The application is a scheduled downloader for Japanese streaming site TVer. It runs on a VPN (Japanese IP required) and tracks downloads to avoid re-downloading.

**Entry point**: `tver_dl/cli.py` → `TVerDownloader` in `core.py`.

**Pipeline** (orchestrated in `core.py`):
1. Load config (`config.py`)
2. Verify Japanese IP via parallel geolocation checks (`vpn.py`)
3. For each series: fetch seasons → fetch episodes from TVer API (`tver_api.py`)
4. Filter episodes by season name and include/exclude title patterns (`filter.py`)
5. Deduplicate against tracker history (`tracker.py`)
6. Download via yt-dlp subprocess (`ytdlp.py`) with Rich progress display (`display.py`)
7. Record result in tracker

Series are processed concurrently using `ThreadPoolExecutor` (default 3 workers, `--max-workers` flag).

## Key Abstractions

**`BaseTracker` (tracker.py)** — abstract interface with two implementations:
- `CSVTracker`: simple flat file, keyed by episode URL
- `DatabaseTracker`: PostgreSQL (tested with Supabase); tables: `series`, `episodes`, `downloads`, `subtitles`

The `subtitles` table and `--subtitles-only` mode work together: it finds already-downloaded episodes that have no subtitle file and retries just the subtitle download without re-downloading video.

**`ConfigManager` (config.py)** — handles platform-specific config paths (XDG on Linux/macOS) and two series config formats:
- **List format**: `series:` is a flat list of series objects
- **Categorized format**: `series:` is a dict where keys are category names; each becomes a subdirectory in `download_path`

Both formats support these per-series fields: `enabled`, `target_seasons` (default `["本編"]`), `subtitles`, `include_patterns`, `exclude_patterns`.

`download_path` and `db_connection_string` support `${ENV_VAR}` expansion.

**`TVerClient` (tver_api.py)** — uses urllib3 + certifi directly (not requests). Requires a browser-style platform session initialization to get `platform_uid`/`platform_token` before fetching series/season/episode data.

**`YtDlpHandler` (ytdlp.py)** — runs yt-dlp as a subprocess and parses its stdout to drive the Rich progress bar. Uses `--print after_move:RESULT:...` to capture the downloaded file path. Custom yt-dlp flags are passed through `yt_dlp_options` in config.

## Docker Setup

`docker-compose.yml` has three services:
- **config**: one-shot `curlimages/curl` container that fetches `config.yaml` from GitHub into a shared volume
- **gluetun**: VPN container (NordVPN/OpenVPN); tver-dl routes all traffic through it via `network_mode: "service:gluetun"`
- **tver-dl**: the downloader; waits for `config` via `condition: service_completed_successfully`

Secrets (`POSTGRESQL_CONNECTION`, VPN credentials) are injected via `.env` file — never hardcoded in the Dockerfile.
