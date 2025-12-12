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
- `archive_file`: Filename for yt-dlp's download archive (tracks downloaded episodes).
- `debug`: Enable verbose logging.
- `subtitles_only`: If true, skips video download and only fetches subtitles.
- `yt_dlp_options`: List of additional command-line options passed to yt-dlp.

**Per-Series Settings:**
- `name`: Friendly name for the series.
- `url`: The TVer series page URL.
- `enabled`: Set to `false` to disable downloading for this series.
- `include_patterns`: List of strings that must appear in the title to download (empty = include all).
- `exclude_patterns`: List of strings that if found in the title, skip download.

## Features

- **Dynamic Output**: Live progress table and download bars using `rich`.
- **Parallel Downloads**: Download multiple series/episodes concurrently.
- **Smart Filtering**: Include/exclude episodes based on title patterns.
- **Archive Tracking**: Prevents re-downloading already fetched episodes.
- **VPN Check**: Ensures you are connected to a Japanese IP before starting.

## License

MIT