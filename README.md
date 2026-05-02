# TVer Auto Downloader

Automatically download new episodes from [TVer](https://tver.jp) series pages using yt-dlp. Requires a Japanese IP (VPN).

## Features

- Live progress bars via Rich
- Parallel series/episode downloads
- Episode filtering by season, title patterns
- Download history tracking (CSV or PostgreSQL)
- Subtitle-only retry mode for missing subtitle files
- Docker deployment with Gluetun VPN tunnel

## Quick Start

**Requirements**: Python 3.10+, yt-dlp, VPN with a Japanese exit node

```bash
pip install git+https://github.com/bry5an/tver-dl.git
tver-dl  # creates config at ~/.config/tver-dl/config.yaml on first run
```

Edit the generated config to add your TVer series URLs, then run again:

```bash
tver-dl
```

Or run from source with UV:

```bash
uv sync
uv run tver-dl
```

## CLI Options

| Flag | Description |
|------|-------------|
| `--config PATH` | Custom config file path |
| `--max-workers N` | Parallel download workers (default: 3) |
| `--subtitles-only` | Retry missing subtitle files without re-downloading video |
| `--skip-vpn-check` | Skip Japanese IP verification |
| `--fetch-episodes URL` | Print episode list for a series URL as JSON |
| `--debug`, `-d` | Enable verbose logging |

## Documentation

- [Configuration Reference](docs/configuration.md) — all config options and series formats
- [Deployment Guide](docs/deployment.md) — Docker, VPN, Ansible
- [Database Setup](docs/database.md) — PostgreSQL/Supabase tracking
- [Architecture](docs/architecture.md) — system design, data flow, module overview
- [Contributing](docs/contributing.md) — dev setup, TVer API exploration, testing

## License

MIT
