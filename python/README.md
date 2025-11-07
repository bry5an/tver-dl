# TVer Auto Downloader

Automatically download new episodes from TVer series pages using yt-dlp.

## Prerequisites

1. **yt-dlp** - Install via Homebrew:
   ```bash
   brew install yt-dlp
   ```

2. **VPN** - Connect to a Japanese server before running the script

3. **uv** - For Python dependency management:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

## Setup

1. Clone or download this project to a folder
2. Navigate to the project folder in Terminal
3. Install dependencies:
   ```bash
   uv pip install -e .
   ```

4. Edit `config.json` to add your series URLs (see Configuration below)

## Configuration

On first run, a `config.json` file will be created. Edit it to add your series:

```json
{
  "series": [
    {
      "name": "Series with Episode Numbers",
      "url": "https://tver.jp/series/sr...",
      "enabled": true,
      "include_patterns": ["＃", "#", "第"],
      "exclude_patterns": ["予告", "ダイジェスト", "解説放送版"]
    },
    {
      "name": "Series Without Numbers (Weekly Show)",
      "url": "https://tver.jp/series/sr...",
      "enabled": true,
      "include_patterns": [],
      "exclude_patterns": ["予告", "番宣", "特報"]
    }
  ],
  "download_path": "./downloads",
  "archive_file": "downloaded.txt",
  "debug": false,
  "yt_dlp_options": [
    "-o", "%(series)s/%(title)s.%(ext)s",
    "--write-sub",
    "--sub-lang", "ja"
  ]
}
```

### Finding Series URLs

1. Go to tver.jp and find your series
2. Look for the series page URL (usually starts with `https://tver.jp/series/`)
3. Copy the full URL into your config

### Configuration Options

**Global Settings:**
- **download_path**: Where to save downloaded files
- **archive_file**: Filename for yt-dlp's download archive (tracks what's been downloaded)
- **debug**: Set to `true` for verbose logging
- **yt_dlp_options**: Additional yt-dlp command-line options

**Per-Series Settings:**
- **name**: A friendly name for the series (for your reference)
- **url**: The TVer series page URL
- **enabled**: Set to `false` to temporarily disable downloading for this series
- **include_patterns**: List of strings that must appear in the title to download (empty = include all)
- **exclude_patterns**: List of strings that if found in title, skip download

### Per-Series Filtering

Each series can have its own filtering rules. This is useful because:
- Some series use `＃1` (full-width), others use `#1` (half-width)
- Some series only host 1 episode at a time (no episode numbers)
- Different series have different types of extras to exclude

**Example 1: Series with episode numbers**
```json
{
  "name": "ちょっとだけエスパー",
  "url": "https://tver.jp/series/srm706pd6g",
  "enabled": true,
  "include_patterns": ["＃", "#"],
  "exclude_patterns": ["予告", "ダイジェスト", "解説放送版", "インタビュー", "メイキング"]
}
```
This will:
- ✅ Include: `＃1　愛してはいけない妻`, `#2　天使`
- ❌ Exclude: `【予告】...`, `＃1【解説放送版】...`, `【インタビュー】...`

**Example 2: Weekly show (no episode numbers)**
```json
{
  "name": "Weekly Variety Show",
  "url": "https://tver.jp/series/sr...",
  "enabled": true,
  "include_patterns": [],
  "exclude_patterns": ["予告", "番宣", "特報"]
}
```
This will:
- ✅ Include: All episodes (even without numbers)
- ❌ Exclude: Only previews and promotional content

**Example 3: Download everything**
```json
{
  "name": "Download All Content",
  "url": "https://tver.jp/series/sr...",
  "enabled": true,
  "include_patterns": [],
  "exclude_patterns": []
}
```

### Common Exclude Patterns

- `予告` - Previews/trailers
- `ダイジェスト` - Digest/recap videos
- `解説放送版` - Audio description versions (for visually impaired)
- `インタビュー` - Interviews
- `メイキング` - Making-of/behind-the-scenes
- `特報` - Special announcements/teasers
- `番宣` - Program promotions
- `みどころ` - Highlights
- `SP` - Special episodes/content
- `総集編` - Compilation episodes

## Usage

1. **Connect to NordVPN** (Japan server)
2. Run the script:
   ```bash
   uv run python tver_downloader.py
   ```
   
   Or if you installed it:
   ```bash
   tver-dl
   ```

3. **Enable debug mode** for troubleshooting:
   ```bash
   uv run python tver_downloader.py --debug
   ```
   
   Or set `"debug": true` in config.json

The script will:
- Check your VPN connection (verifies you're connecting from Japan)
- Scan each enabled series for episodes
- Download any new episodes not in your history
- Save a record in `downloaded.json` to avoid re-downloading

## How It Works

1. **VPN Check**: Verifies you're connected via Japanese IP using ipapi.co
2. **Episode Discovery**: Scrapes the series page for episode links using yt-dlp
3. **Filtering**: Applies per-series include/exclude patterns
4. **Download**: Uses yt-dlp to download episodes
5. **Duplicate Detection**: yt-dlp's `--download-archive` automatically tracks and skips already downloaded episodes

### Download Archive

The script uses yt-dlp's built-in `--download-archive` feature to track downloaded episodes. This creates a `downloaded.txt` file (configurable) that contains IDs of all downloaded videos. On subsequent runs, yt-dlp automatically skips anything already in this archive file.

**Benefits:**
- More reliable than manual tracking
- Works even if you delete the video files
- Standard yt-dlp feature used by many tools
- No separate state file management needed

## Files

- `tver_downloader.py` - Main script
- `config.json` - Your series configuration (created on first run)
- `downloads/` - Default download folder (configurable)
- `downloads/downloaded.txt` - yt-dlp's download archive (automatically maintained)

## Troubleshooting

### Enable Debug Mode

Run with debug flag for detailed logging:
```bash
uv run python tver_downloader.py --debug
```

Or add to config.json:
```json
{
  "debug": true,
  "series": [...]
}
```

### "yt-dlp not found"
Install yt-dlp: `brew install yt-dlp`

### "Not connected to Japan VPN"
Connect to NordVPN and select a Japanese server before running

### "No episodes found"

The script tries two methods to find episodes:
1. **yt-dlp extraction** - Uses yt-dlp's built-in series parsing
2. **TVer API** - Direct API calls to TVer's platform

If both fail:
- Run with `--debug` to see detailed error messages
- Check that the series URL is correct (should be `https://tver.jp/series/...`)
- Try running yt-dlp directly: `yt-dlp --flat-playlist https://tver.jp/series/YOUR_SERIES_ID`
- The TVer page structure or API may have changed

### Downloads fail
- Ensure you're connected to NordVPN (Japan)
- Run with `--debug` for detailed error messages
- Try downloading an episode URL manually with yt-dlp to see the error:
  ```bash
  yt-dlp https://tver.jp/episodes/EPISODE_ID
  ```
- TVer may have changed their DRM or streaming method
- Check yt-dlp is up to date: `brew upgrade yt-dlp`

## Advanced Usage

### Custom yt-dlp Options

Edit `yt_dlp_options` in `config.json`. Examples:

```json
"yt_dlp_options": [
  "-o", "%(series)s/S01E%(episode_number)s - %(title)s.%(ext)s",
  "--write-sub",
  "--sub-lang", "ja",
  "--format", "best",
  "--write-thumbnail"
]
```

### Multiple Series

Add multiple entries to the `series` array:

```json
{
  "series": [
    {
      "name": "Series 1",
      "url": "https://tver.jp/series/...",
      "enabled": true
    },
    {
      "name": "Series 2", 
      "url": "https://tver.jp/series/...",
      "enabled": true
    }
  ]
}
```

## Future Enhancements

- [ ] Automatic scheduling with cron/launchd
- [ ] NordVPN auto-connection
- [ ] Better episode metadata detection
- [ ] Notification system when new episodes are downloaded
- [ ] GUI for managing series

## License

MIT - Use freely!