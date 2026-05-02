# Configuration Reference

The config file is auto-created on first run:

- **Linux/macOS**: `~/.config/tver-dl/config.yaml`
- **Windows**: `%APPDATA%\tver-dl\config.yaml`

Pass a custom path with `--config PATH`.

## Full Example

```yaml
download_path: ./downloads        # supports ${ENV_VAR} expansion
archive_file: downloaded.txt      # legacy yt-dlp archive (optional)

history:
  type: csv                       # "csv" (default) or "database"
  csv_path: history.csv           # relative to download_path
  db_connection_string: "postgresql://user:pass@host:5432/db"  # required if type=database

debug: false
subtitles_only: false

yt_dlp_options:
  - "-o"
  - "%(series)s/%(title)s.%(ext)s"
  - "--write-sub"
  - "--sub-lang"
  - "ja"

series:
  dramas:
    - name: "Series With Episode Numbers"
      url: "https://tver.jp/series/sr..."
      include_patterns:
        - "＃"
        - "#"
        - "第"
      exclude_patterns:
        - "予告"
        - "ダイジェスト"

  variety_shows:
    - name: "Weekly Variety Show"
      url: "https://tver.jp/series/sr..."
      exclude_patterns:
        - "予告"
        - "番宣"

  kids_shows:
    - name: "Kids Show Without Subtitles"
      url: "https://tver.jp/series/sr..."
      subtitles: false
```

## Global Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `download_path` | string | `./downloads` | Directory for downloaded files. Supports `${ENV_VAR}`. |
| `archive_file` | string | — | Legacy yt-dlp archive filename (relative to `download_path`). |
| `debug` | bool | `false` | Enable verbose logging. |
| `subtitles_only` | bool | `false` | Skip video download; only fetch subtitles. |
| `yt_dlp_options` | list | `[]` | Extra flags passed to yt-dlp. |

## History / Tracking

```yaml
history:
  type: csv          # or "database"
  csv_path: history.csv
  db_connection_string: "postgresql://..."   # required for type=database
```

See [Database Setup](database.md) for PostgreSQL/Supabase configuration.

## Series Format

Two formats are supported:

### List Format

`series` is a flat list — all downloads go to `download_path`:

```yaml
series:
  - name: "Show Name"
    url: "https://tver.jp/series/sr..."
```

### Categorized Format

`series` is a dict — each key becomes a subdirectory under `download_path`:

```yaml
series:
  dramas:
    - name: "Drama Name"
      url: "https://tver.jp/series/sr..."
  variety:
    - name: "Variety Show"
      url: "https://tver.jp/series/sr..."
```

Downloads for the `dramas` category go to `{download_path}/dramas/`.

## Per-Series Options

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `name` | string | required | Friendly label for logs and tracker. |
| `url` | string | required | TVer series page URL. |
| `enabled` | bool | `true` | Set `false` to skip without removing the entry. |
| `target_seasons` | list | `["本編"]` | Season names to download. Must match exactly. |
| `subtitles` | bool | `true` | Include in `--subtitles-only` runs. |
| `include_patterns` | list | `[]` | Episode title must contain at least one pattern (empty = include all). |
| `exclude_patterns` | list | `[]` | Episode title must not contain any pattern. |

### Filter Priority

1. **Season**: if `target_seasons` is set, episode's `season_name` must match one entry.
2. **Exclude**: if any `exclude_patterns` match the title, skip.
3. **Include**: if `include_patterns` is non-empty, at least one must match.
4. Otherwise: download.
