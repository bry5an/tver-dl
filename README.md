# TVer Auto Downloader

Automatically download new episodes from TVer series pages using yt-dlp.

## Prerequisites

1. **Python 3.10+**
2. **yt-dlp** - Install via Homebrew or pip:
   ```bash
   brew install yt-dlp
   # or
   pip install yt-dlp
   ```
3. **VPN** - Connect to a Japanese server before running the script (e.g., NordVPN, ProtonVPN).

## Installation

Clone the repository and install the package:

```bash
git clone https://github.com/bry5an/tver-dl.git
cd tver-dl
pip install .
```

Or run locally with UV:
```bash
uv run .
```

## Usage

Run the tool from the command line:

```bash
tver-dl
```

### Options

- `--version`: Show the version number.
- `--debug`, `-d`: Enable debug logging.
- `--config CONFIG`: Specify a custom configuration file path.
- `--fetch-episodes URL`: Fetch and print episodes for a specific series URL (JSON output).
- `--skip-vpn-check`: Skip the VPN connection check.
- `--subtitles-only`: Only download missing subtitle files.
- `--max-workers N`: Set the maximum number of parallel downloads (default: 3).

## Configuration

The configuration file is automatically created on the first run at:
- **Linux/macOS**: `~/.config/tver-dl/config.yaml`
- **Windows**: `%APPDATA%\tver-dl\config.yaml`

You can edit this file to add your series and customize settings.

### Example `config.yaml`

```yaml
download_path: ./downloads
archive_file: downloaded.txt
history:
  type: csv # or "database"
  csv_path: history.csv
  db_connection_string: postgresql://user:pass@host:5432/db

debug: false
subtitles_only: false

yt_dlp_options:
  - "-o"
  - "%(series)s/%(title)s.%(ext)s"
  - "--write-sub"
  - "--sub-lang"
  - "ja"

series:
  - name: "Series with Episode Numbers"
    url: "https://tver.jp/series/sr..."
    enabled: true
    include_patterns:
      - "＃"
      - "#"
      - "第"
    exclude_patterns:
      - "予告"
      - "ダイジェスト"
      - "解説放送版"

  - name: "Weekly Variety Show"
    url: "https://tver.jp/series/sr..."
    enabled: true
    include_patterns: []
    exclude_patterns:
      - "予告"
      - "番宣"
      - "特報"
```

### Configuration Options

**Global Settings:**
- `download_path`: Directory to save downloaded files.
- `archive_file`: (Legacy) Filename for old `yt-dlp` download archive.
- `history`: Configuration for download tracking.
    - `type`: `csv` (default) or `database`.
    - `csv_path`: Filename for CSV history (relative to `download_path`).
    - `db_connection_string`: PostgreSQL connection URL (required if `type` is `database`).
- `debug`: Enable verbose logging.
- `subtitles_only`: If true, skips video download and only fetches subtitles.
- `yt_dlp_options`: List of additional command-line options passed to yt-dlp.

**Per-Series Settings:**
- `name`: Friendly name for the series.
- `url`: The TVer series page URL.
- `enabled`: Set to `false` to disable downloading for this series.
- `include_patterns`: List of strings that must appear in the title to download (empty = include all).
- `exclude_patterns`: List of strings that if found in the title, skip download.

## Database Tracking Setup

If you prefer to track downloads in a PostgreSQL database (e.g., Supabase) instead of a CSV file:

1. **Create the Database Tables**:
   Run the SQL scripts located in the `sql/` directory of this repository in your database. Execute them in the following order:
   - `sql/series_table.sql`
   - `sql/episodes_table.sql`
   - `sql/downloads_table.sql`

2. **Configure `config.yaml`**:
   Update your configuration file to use the `database` history type and provide your connection string.

   ```yaml
   history:
     type: "database"
     db_connection_string: "postgresql://user:password@hostname:5432/dbname"
     # db_connection_string: "${DATABASE_URL}" # if using environment variables
   ```

   **Supabase Users**:
   Supabase's direct database connection is IPv6-only (unless you have the IPv4 add-on). If you see `No route to host` errors:
   1. Use the **Session** mode connection string from the **Connection Pooler** settings (port 5432).
   2. Or ensure your network supports IPv6.

## Features

- **Dynamic Output**: Live progress table and download bars using `rich`. # WIP
- **Parallel Downloads**: Download multiple series/episodes concurrently.
- **Smart Filtering**: Include/exclude episodes based on title patterns.
- **Archive Tracking**: Prevents re-downloading already fetched episodes.
- **VPN Check**: Ensures you are connected to a Japanese IP before starting.

## License

MIT