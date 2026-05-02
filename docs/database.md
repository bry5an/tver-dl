# Database Setup

tver-dl supports PostgreSQL for download history tracking (default is CSV). Supabase works well as a managed option.

## Schema

Run the SQL scripts in `sql/` in this order:

```bash
psql $DATABASE_URL -f sql/series_table.sql
psql $DATABASE_URL -f sql/episodes_table.sql
psql $DATABASE_URL -f sql/downloads_table.sql
psql $DATABASE_URL -f sql/subtitles_table.sql  # optional: subtitle tracking
psql $DATABASE_URL -f sql/rls_rules.sql        # optional: Supabase row-level security
```

### Tables

```mermaid
erDiagram
    series {
        uuid id PK
        text tver_series_id
        text name
        text url
        bool has_subtitles
        timestamp created_at
        timestamp updated_at
    }
    episodes {
        uuid id PK
        uuid series_id FK
        text tver_episode_id
        text title
        int episode_number
        text episode_url
        timestamp subtitles_checked_at
    }
    downloads {
        uuid id PK
        uuid episode_id FK
        text status
        timestamp downloaded_at
        text file_path
        bigint file_size_bytes
        text downloader_host
    }
    subtitles {
        uuid id PK
        uuid episode_id FK
        text status
        timestamp checked_at
        timestamp downloaded_at
        text subtitle_format
        text series_name
        text episode_title
    }
    series ||--o{ episodes : "has"
    episodes ||--o{ downloads : "has"
    episodes ||--o{ subtitles : "has"
```

## Config

```yaml
history:
  type: database
  db_connection_string: "postgresql://user:password@hostname:5432/dbname"
```

Environment variable expansion is supported:

```yaml
history:
  type: database
  db_connection_string: "${DATABASE_URL}"
```

## Supabase

Supabase's direct connection is **IPv6-only** unless you have the IPv4 add-on. If you see `No route to host`:

1. Use the **Session mode** connection string from **Project Settings → Database → Connection Pooler** (port 5432).
2. Or ensure your host has IPv6 connectivity.

## Subtitles-Only Mode

The `subtitles` table tracks which episodes have subtitle files. Running `--subtitles-only` will:

1. Query `get_episodes_needing_subtitles()` for each series
2. Re-run yt-dlp with `--skip-download --write-subs --sub-lang ja`
3. Update the `subtitles` table with the result

Per-series `subtitles: false` excludes that series from subtitles-only runs.
