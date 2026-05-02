# Contributing

## Dev Setup

```bash
git clone https://github.com/bry5an/tver-dl.git
cd tver-dl
uv sync
```

Run:

```bash
uv run tver-dl --config config.yaml
```

Lint and format:

```bash
uvx ruff check .
uvx ruff format .
```

Tests:

```bash
uv run pytest
```

Pre-commit hooks:

```bash
pre-commit install
```

## Project Structure

```
tver_dl/       # main package
scripts/       # one-off inspection scripts
sql/           # database schema files
tests/         # pytest test suite
ansible/       # file-sync playbook
```

See [Architecture](architecture.md) for a module-level overview.

## Inspecting the TVer API

This is useful when you want to find new metadata fields for better episode filtering (e.g. boolean flags for "preview" vs "real episode").

### Step 1 — Get Platform Tokens

```bash
curl -X POST "https://platform-api.tver.jp/v2/api/platform_users/browser/create" \
     -H "Origin: https://tver.jp" \
     -H "Referer: https://tver.jp/" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "device_type=pc"
```

Extract `result.platform_uid` and `result.platform_token` from the response.

### Step 2 — Get Series Seasons

Find your `series_id` from the TVer URL (e.g. `https://tver.jp/series/sr9gfdf2ex` → `sr9gfdf2ex`).

```bash
curl "https://service-api.tver.jp/api/v1/callSeriesSeasons/sr9gfdf2ex" \
     -H "x-tver-platform-type: web"
```

Look for items where `type` is `season`; note `content.id` (the season ID).

### Step 3 — Get Episodes for a Season

```bash
curl "https://platform-api.tver.jp/service/api/v1/callSeasonEpisodes/{season_id}?platform_uid={uid}&platform_token={token}" \
     -H "x-tver-platform-type: web" \
     -H "x-tver-platform-token: {token}" \
     -H "x-tver-platform-uid: {uid}"
```

Useful fields in the response:

| Field | Example | Use |
|-------|---------|-----|
| `broadcastDateLabel` | `"3月5日(日)放送"` | Broadcast date string |
| `isHighlight` | `true/false` | Often marks digest episodes |
| `no` | `12` | Episode number |
| `content.title` | `"Episode Title"` | Episode title |
| `content.seriesTitle` | `"Series Name"` | Series name |

`scripts/get_episodes.py` automates these steps and writes JSON output to `scripts/json_output/`.

### Extending Filtering

If you find a useful field:

1. Extract it in `TVerClient.get_series_episodes()` (`tver_dl/tver_api.py`)
2. Add filtering logic in `EpisodeFilter.should_download()` (`tver_dl/filter.py`)
3. Add tests in `tests/test_filter.py`
