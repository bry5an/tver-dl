#!/usr/bin/env python3
"""
TVer Auto Downloader
Downloads new episodes from TVer series pages using yt-dlp
"""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Try to import required packages
try:
    import requests
except ImportError:
    print("Installing required packages with uv...")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests


class TVerDownloader:
    def __init__(self, config_path: str = "config.json", debug: bool = False):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.debug = debug or self.config.get("debug", False)

        # Setup logging
        log_level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=log_level, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
        self.logger = logging.getLogger(__name__)
        self.download_report = {}  # Track downloads by series

    def load_config(self) -> Dict:
        """Load configuration file"""
        if not self.config_path.exists():
            default_config = {
                "series": [
                    {
                        "name": "Example Series",
                        "url": "https://tver.jp/series/...",
                        "enabled": True,
                        "include_patterns": ["＃", "#", "第"],
                        "exclude_patterns": ["予告", "ダイジェスト", "解説放送版"],
                    }
                ],
                "download_path": "./downloads",
                "archive_file": "downloaded.txt",
                "debug": False,
                "yt_dlp_options": [
                    "-o",
                    "%(series)s/%(title)s.%(ext)s",
                    "--write-sub",
                    "--sub-lang",
                    "ja",
                ],
            }
            self.config_path.write_text(json.dumps(default_config, indent=2, ensure_ascii=False))
            print(f"Created default config at {self.config_path}")
            print("Please edit the config file to add your series URLs")
            return default_config

        config = json.loads(self.config_path.read_text())
        
        # Expand environment variables in download_path
        if "download_path" in config:
            config["download_path"] = os.path.expandvars(config["download_path"])
        
        return config

    def check_vpn_connection(self) -> bool:
        """Check if connected to a VPN (trying multiple IP geolocation services)"""
        try:
            self.logger.info("Checking VPN connection...")

            # Try multiple geolocation services
            services = [
                ("https://ipapi.co/json/", lambda r: r.json().get("country_code")),
                ("https://ip.seeip.org/geoip", lambda r: r.json().get("country_code")),
                ("https://api.myip.com", lambda r: r.json().get("cc")),
            ]

            for url, parser in services:
                try:
                    response = requests.get(url, timeout=5)
                    response.raise_for_status()
                    country = parser(response)
                    ip = response.json().get("ip", "unknown")

                    if country:
                        if country == "JP":
                            self.logger.info(f"✓ Connected via Japan IP ({ip})")
                            return True
                        else:
                            self.logger.warning(
                                f"Not connected to Japan VPN (detected: {country}, IP: {ip})"
                            )
                            print("  TVer downloads may fail without Japanese IP")
                            response = input("Continue anyway? (y/n): ")
                            return response.lower() == "y"
                except Exception as e:
                    self.logger.debug(f"Service {url} failed: {e}")
                    continue

            # If all services failed
            self.logger.error("Could not verify IP location from any service")
            print("  Unable to verify VPN connection")
            response = input("Continue anyway? (y/n): ")
            return response.lower() == "y"

        except Exception as e:
            self.logger.error(f"VPN check failed: {e}")
            response = input("Continue anyway? (y/n): ")
            return response.lower() == "y"

    def should_download_episode(self, title: str, series_config: Dict) -> bool:
        """Check if episode should be downloaded based on series-specific filters"""

        # If no filtering configured for this series, download everything
        include_patterns = series_config.get("include_patterns", [])
        exclude_patterns = series_config.get("exclude_patterns", [])

        if not include_patterns and not exclude_patterns:
            self.logger.debug(f"  No filters configured, including: {title}")
            return True

        self.logger.debug(f"Checking episode: {title}")

        # First, check exclude patterns
        for pattern in exclude_patterns:
            if pattern in title:
                self.logger.debug(f"  -> Excluded (matched exclude pattern '{pattern}')")
                return False

        # If include patterns are specified, title must match at least one
        if include_patterns:
            for pattern in include_patterns:
                if pattern in title:
                    self.logger.debug(f"  -> Included (matched include pattern '{pattern}')")
                    return True
            # Didn't match any include pattern
            self.logger.debug("  -> Excluded (no include pattern matched)")
            return False

        # No include patterns, and didn't match exclude patterns
        self.logger.debug("  -> Included (passed all filters)")
        return True

    def get_episode_urls_ytdlp(self, series_url: str) -> List[Dict[str, str]]:
        """Use yt-dlp to extract episode URLs from a series page"""
        try:
            self.logger.info(f"Using yt-dlp to extract episodes from: {series_url}")

            # Use yt-dlp's --flat-playlist to get all episode URLs without downloading
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--print",
                "%(id)s|%(title)s|%(webpage_url)s",
                "--no-warnings",
                "--playlist-items",
                "1-10",
                series_url,
            ]

            self.logger.debug(f"Running command: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                self.logger.error(f"yt-dlp extraction failed: {result.stderr}")
                return []

            episodes = []
            for line in result.stdout.strip().splitlines():
                if not line or "|" not in line:
                    continue

                parts = line.split("|", 2)
                if len(parts) >= 3:
                    episode_id = parts[0]
                    title = parts[1]
                    episode_url = parts[2]

                    if episode_url and title:
                        episodes.append({"url": episode_url, "title": title, "id": episode_id})
                        self.logger.debug(f"Found episode: {title} - {episode_url}")

            self.logger.info(f"yt-dlp found {len(episodes)} episode(s)")
            return episodes

        except subprocess.TimeoutExpired:
            self.logger.error("yt-dlp command timed out")
            return []
        except FileNotFoundError:
            self.logger.error("yt-dlp not found. Please install it: brew install yt-dlp")
            return []
        except Exception as e:
            self.logger.error(f"Error extracting episodes with yt-dlp: {e}", exc_info=self.debug)
            return []

    def get_episode_urls_api(self, series_url: str) -> List[Dict[str, str]]:
        """Try to get episodes via TVer's API"""
        try:
            # Extract series ID from URL
            match = re.search(r"/series/([^/]+)", series_url)
            if not match:
                self.logger.warning("Could not extract series ID from URL")
                return []

            series_id = match.group(1)
            self.logger.info(f"Attempting to fetch episodes via API for series: {series_id}")

            # TVer API endpoint
            api_url = f"https://platform-api.tver.jp/service/api/v1/callSeriesEpisodes/{series_id}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Origin": "https://tver.jp",
                "Referer": series_url,
                "x-tver-platform-type": "web",
            }

            self.logger.debug(f"API request URL: {api_url}")
            response = requests.get(api_url, headers=headers, timeout=15)
            response.raise_for_status()

            data = response.json()
            self.logger.debug(f"API response keys: {data.keys()}")

            episodes = []
            # TVer API can have different structures - try multiple paths
            if "result" in data and "contents" in data["result"]:
                episode_list = data["result"]["contents"]
            elif "episodes" in data:
                episode_list = data["episodes"]
            elif isinstance(data, list):
                episode_list = data
            else:
                self.logger.debug(f"Unexpected API response structure. Keys: {data.keys()}")
                episode_list = []

            for ep in episode_list:
                # Try different ways to get episode ID and title
                episode_id = ep.get("id") or ep.get("episodeID") or ep.get("content", {}).get("id")
                title = (
                    ep.get("title")
                    or ep.get("episodeTitle")
                    or ep.get("content", {}).get("title")
                    or ep.get("broadcastDateLabel", "")
                )

                if episode_id:
                    episode_url = f"https://tver.jp/episodes/{episode_id}"

                    # Some series might have series name in title already, clean it if needed
                    if title:
                        episodes.append({"url": episode_url, "title": title, "id": episode_id})
                        self.logger.debug(f"Found episode via API: {title} - {episode_url}")

            if episodes:
                self.logger.info(f"API found {len(episodes)} episode(s)")
            else:
                self.logger.warning("API returned data but couldn't parse episodes")
                if self.debug:
                    self.logger.debug(
                        f"API response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}"
                    )

            return episodes

        except Exception as e:
            self.logger.warning(f"API extraction failed: {e}", exc_info=self.debug)
            return []

    def get_episode_urls(self, series_url: str) -> List[Dict[str, str]]:
        """Get episode URLs using multiple methods"""
        episodes = []

        # Try method 1: TVer API (faster)
        self.logger.info("Method 1: Trying TVer API...")
        episodes = self.get_episode_urls_api(series_url)

        # Try method 2: yt-dlp if API fails (slower but more reliable)
        if not episodes:
            self.logger.info("Method 2: Trying yt-dlp extraction (this may take a minute)...")
            episodes = self.get_episode_urls_ytdlp(series_url)

        # Remove duplicates based on URL
        seen_urls = set()
        unique_episodes = []
        for ep in episodes:
            if ep["url"] not in seen_urls:
                seen_urls.add(ep["url"])
                unique_episodes.append(ep)

        if not unique_episodes:
            self.logger.warning("No episodes found using any method")
            self.logger.info("You can try manually adding episode URLs to download in the config")

        return unique_episodes

    def download_episodes(
        self, episodes: List[Dict[str, str]], series_name: str, series_config: Dict
    ) -> int:
        """Download episodes using yt-dlp with archive support"""
        if not episodes:
            return 0

        try:
            download_path = self.config.get("download_path", "./downloads")
            Path(download_path).mkdir(parents=True, exist_ok=True)

            # Use yt-dlp's download archive feature
            archive_file = self.config.get("archive_file", "downloaded.txt")
            archive_path = Path(download_path) / archive_file

            # Build list of URLs to download
            episode_urls = [ep["url"] for ep in episodes]

            # Build yt-dlp command
            cmd = [
                "yt-dlp",
                "--download-archive",
                str(archive_path),
                *self.config.get("yt_dlp_options", []),
                "-P",
                download_path,
                *episode_urls,
            ]

            if self.debug:
                cmd.append("-v")  # Verbose output in debug mode

            self.logger.debug(f"Download command: {' '.join(cmd)}")
            self.logger.info(f"Downloading {len(episodes)} episode(s) with yt-dlp...")
            self.logger.info("(yt-dlp will skip already downloaded episodes)")

            # Initialize series in report if not exists
            if series_name not in self.download_report:
                self.download_report[series_name] = []

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                # Parse yt-dlp output to find successfully downloaded episodes
                for line in result.stdout.splitlines():
                    if "[download] Destination:" in line:
                        episode_title = line.split("Destination: ")[-1].split("/")[-1]
                        self.download_report[series_name].append(episode_title)

                self.logger.info("✓ Download process completed")
                return len(episodes)
            else:
                self.logger.error("✗ Download process had errors")
                return 0

        except FileNotFoundError:
            self.logger.error("✗ Error: yt-dlp not found. Please install it:")
            self.logger.error("  brew install yt-dlp")
            return 0
        except Exception as e:
            self.logger.error(f"✗ Download error: {e}", exc_info=self.debug)
            return 0

    def process_series(self, series: Dict) -> int:
        """Process a single series and download new episodes"""
        series_name = series["name"]
        series_url = series["url"]

        print(f"\n{'=' * 60}")
        self.logger.info(f"Processing: {series_name}")
        self.logger.info(f"URL: {series_url}")
        print(f"{'=' * 60}")

        # Get episodes from series page
        all_episodes = self.get_episode_urls(series_url)

        if not all_episodes:
            self.logger.warning("No episodes found on series page")
            return 0

        self.logger.info(f"Found {len(all_episodes)} episode(s)")

        # Filter episodes based on series-specific patterns
        episodes_to_download = []
        for ep in all_episodes:
            if self.should_download_episode(ep["title"], series):
                episodes_to_download.append(ep)

        if not episodes_to_download:
            self.logger.info("No episodes match the filter criteria")
            return 0

        if len(episodes_to_download) < len(all_episodes):
            excluded_count = len(all_episodes) - len(episodes_to_download)
            self.logger.info(
                f"Filtered to {len(episodes_to_download)} episode(s) (excluded {excluded_count})"
            )

        # Check archive file for already-downloaded episodes
        archive_path = Path(self.config.get("download_path", "./downloads")) / self.config.get("archive_file", "downloaded.txt")
        downloaded_urls = set()
        if archive_path.exists():
            downloaded_urls = set(archive_path.read_text().splitlines())

        # Split episodes into new vs already downloaded
        new_episodes = [ep for ep in episodes_to_download if ep["url"] not in downloaded_urls]
        already_downloaded = [ep for ep in episodes_to_download if ep["url"] in downloaded_urls]

        if not new_episodes:
            self.logger.info("All matching episodes already downloaded.")
            return 0

        self.logger.info(f"\nEpisodes to download ({len(new_episodes)} new, {len(already_downloaded)} skipped):")
        for i, ep in enumerate(new_episodes, 1):
            print(f"  {i}. {ep['title']}")

        # Download only new ones
        return self.download_episodes(new_episodes, series_name, series)

    def run(self, skip_vpn_check: bool = False, max_workers: int = 3):
        """Main execution method"""
        print("TVer Auto Downloader")
        print("=" * 60)

        if self.debug:
            self.logger.info("DEBUG MODE ENABLED")

        # Check VPN
        if not skip_vpn_check and not self.check_vpn_connection():
            print("\nExiting...")
            return

        # Get enabled series
        enabled_series = [s for s in self.config.get("series", []) if s.get("enabled", True)]

        if not enabled_series:
            self.logger.warning("\nNo enabled series in config.json")
            return

        self.logger.info(f"\nProcessing {len(enabled_series)} series...")
        self.logger.info(f"Using {max_workers} worker(s) for downloads")

        total_downloaded = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.process_series, s): s for s in enabled_series}
            for future in as_completed(futures):
                series = futures[future]
                try:
                    total_downloaded += future.result()
                except Exception as e:
                    self.logger.error(f"Error processing {series.get('name')}: {e}", exc_info=self.debug)

        # Display download report
        if any(self.download_report.values()):
            print("\nDownload Summary")
            print("=" * 60)
            for series_name, episodes in self.download_report.items():
                if episodes:
                    print(f"\n{series_name} ({len(episodes)} downloaded):")
                    for ep in episodes:
                        print(f"  - {ep}")
        else:
            print("\nNo new episodes were downloaded.")


        print(f"\n{'=' * 60}")
        self.logger.info(f"Complete! Processed {total_downloaded} episode(s)")
        print(f"{'=' * 60}")

def fetch_episodes_only(series_url: str):
    """Fetch episodes and output as JSON for the app"""
    downloader = TVerDownloader(debug=False)
    episodes = downloader.get_episode_urls(series_url)
    import json
    print(json.dumps(episodes))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', '-d', action='store_true')
    parser.add_argument('--fetch-episodes', help='Fetch episodes for a series URL')
    parser.add_argument('--config', help='Config file path')
    parser.add_argument('--skip-vpn-check', action='store_true', help='Skip VPN connection check')
    parser.add_argument('--max-workers', type=int, default=3, help='Maximum number of parallel downloads (default: 3)')
    
    args = parser.parse_args()
    
    if args.fetch_episodes:
        fetch_episodes_only(args.fetch_episodes)
        return
    
    downloader = TVerDownloader(
        config_path=args.config if args.config else "config.json",
        debug=args.debug
    )
    downloader.run(skip_vpn_check=args.skip_vpn_check, max_workers=args.max_workers)

if __name__ == "__main__":
    main()
