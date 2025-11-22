import argparse
import json
import logging
from pathlib import Path

from .core import TVerDownloader
from .ytdlp import YtDlpHandler

def fetch_episodes_only(series_url: str):
    """Fetch episodes and output as JSON (helper for external apps)."""
    # Minimal setup for fetching
    logging.basicConfig(level=logging.ERROR)
    handler = YtDlpHandler({}, logging.getLogger("fetcher"))
    episodes = handler.extract_episodes(series_url)
    print(json.dumps(episodes))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", "-d", action="store_true")
    parser.add_argument("--fetch-episodes", help="Fetch episodes for a series URL")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--skip-vpn-check", action="store_true", help="Skip VPN connection check")
    parser.add_argument("--subtitles-only", action="store_true", help="Only download missing subtitle files")
    parser.add_argument("--max-workers", type=int, default=3, help="Maximum number of parallel downloads")

    args = parser.parse_args()

    if args.fetch_episodes:
        fetch_episodes_only(args.fetch_episodes)
        return

    downloader = TVerDownloader(
        config_path=args.config,
        debug=args.debug,
        subtitles_only=args.subtitles_only,
    )
    downloader.run(skip_vpn_check=args.skip_vpn_check, max_workers=args.max_workers)

if __name__ == "__main__":
    main()
