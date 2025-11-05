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
from html import unescape
from pathlib import Path
from typing import Dict, List

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
        logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
        self.logger = logging.getLogger(__name__)

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

        return json.loads(self.config_path.read_text())

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
                            self.logger.warning(f"Not connected to Japan VPN (detected: {country}, IP: {ip})")
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
        include_patterns = series_config.get("include_patterns", [])
        exclude_patterns = series_config.get("exclude_patterns", [])

        self.logger.debug(f"Checking episode: {title}")

        # First check exclude patterns - if any match, reject immediately
        for pattern in exclude_patterns:
            if pattern in title:
                self.logger.debug(f"  -> Excluded (matched exclude pattern '{pattern}')")
                return False

        # If no include patterns are specified, accept anything that wasn't excluded
        if not include_patterns:
            self.logger.debug("  -> Included (no include patterns specified)")
            return True

        # With include patterns, at least one must match
        for pattern in include_patterns:
            if pattern in title:
                self.logger.debug(f"  -> Included (matched include pattern '{pattern}')")
                return True

        # If we get here, no include pattern matched
        self.logger.debug("  -> Excluded (no include pattern matched)")
        return False

    def _get_title_from_webpage(self, url: str) -> str | None:
        """Try to fetch the episode title from the episode webpage (og:title / twitter:title / <title> / JSON)."""
        if not url:
            return None
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            html = resp.text

            # Try multiple patterns / orders to find og:title / twitter:title / regular <title>
            patterns = [
                r'<meta[^>]+(?:property|name)\s*=\s*["\']og:title["\'][^>]*content\s*=\s*["\']([^"\']+)["\']',
                r'<meta[^>]+content\s*=\s*["\']([^"\']+)["\'][^>]+(?:property|name)\s*=\s*["\']og:title["\']',
                r'<meta[^>]+name\s*=\s*["\']twitter:title["\'][^>]*content\s*=\s*["\']([^"\']+)["\']',
                r'"og:title"\s*:\s*["\']([^"\']+)["\']',  # JSON-like
                r"<title[^>]*>(.*?)</title>",
            ]

            for pat in patterns:
                m = re.search(pat, html, re.I | re.S)
                if m:
                    title = unescape(m.group(1).strip())
                    if title:
                        self.logger.debug(f"Fetched title from page: {title!r} ({url})")
                        print(f"  Fetched title: {title}")
                        return title

        except Exception as e:
            self.logger.debug(f"Could not fetch title from page {url}: {e}")
        return None

    def get_episode_urls_ytdlp(self, series_url: str) -> List[Dict[str, str]]:
        """Use yt-dlp to extract episode URLs from a series page"""
        try:
            self.logger.info(f"Using yt-dlp to extract episodes from: {series_url}")

            # Use yt-dlp's --flat-playlist to get all episode URLs without downloading
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--no-warnings",
                series_url,
            ]

            self.logger.debug(f"Running command: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                self.logger.error(f"yt-dlp extraction failed: {result.stderr}")
                return []

            episodes = []
            for line in result.stdout.strip().splitlines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    self.logger.debug(f"Could not parse JSON line: {line[:100]}...")
                    continue

                episode_url = data.get("url") or data.get("webpage_url") or data.get("id")
                if episode_url and not episode_url.startswith("http"):
                    episode_url = f"https://tver.jp/episodes/{episode_url}"

                title = data.get("title")
                print(f"  Extracted title: {title} - {episode_url}")
                if not title:
                    # try to fetch from episode page (more reliable for tver)
                    title = self._get_title_from_webpage(data.get("webpage_url") or episode_url)

                # fallback to a useful placeholder if still missing
                if not title:
                    title = data.get("webpage_url_basename") or episode_url or data.get("id", "")

                episodes.append({"url": episode_url, "title": title, "id": data.get("id", "")})
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
        """Try to get episodes via TVer's API (experimental)"""
        try:
            # Extract series ID from URL
            match = re.search(r"/series/([^/]+)", series_url)
            if not match:
                self.logger.warning("Could not extract series ID from URL")
                return []

            series_id = match.group(1)
            self.logger.info(f"Attempting to fetch episodes via API for series: {series_id}")

            # TVer API endpoint (may need adjustment)
            api_url = f"https://platform-api.tver.jp/service/api/v1/callSeriesEpisodes/{series_id}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Origin": "https://tver.jp",
                "Referer": series_url,
            }

            self.logger.debug(f"API request URL: {api_url}")
            response = requests.get(api_url, headers=headers, timeout=15)
            response.raise_for_status()

            data = response.json()
            self.logger.debug(f"API response keys: {data.keys()}")

            episodes = []
            # Parse API response (structure may vary)
            episode_list = data.get("result", {}).get("contents", [])

            for ep in episode_list:
                episode_id = ep.get("id") or ep.get("content", {}).get("id")
                if episode_id:
                    episode_url = f"https://tver.jp/episodes/{episode_id}"
                    title = ep.get("title") or ep.get("content", {}).get("title", episode_id)

                    episodes.append({"url": episode_url, "title": title, "id": episode_id})
                    self.logger.debug(f"Found episode via API: {title} - {episode_url}")

            self.logger.info(f"API found {len(episodes)} episode(s)")
            return episodes

        except Exception as e:
            self.logger.warning(f"API extraction failed: {e}", exc_info=self.debug)
            return []

    def get_episode_urls(self, series_url: str) -> List[Dict[str, str]]:
        """Get episode URLs using multiple methods"""
        episodes = []

        # Try method 1: yt-dlp extraction (most reliable)
        self.logger.info("Method 1: Trying yt-dlp extraction...")
        episodes = self.get_episode_urls_ytdlp(series_url)

        # Try method 2: API if yt-dlp fails
        if not episodes:
            self.logger.info("Method 2: Trying TVer API...")
            episodes = self.get_episode_urls_api(series_url)

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

    def download_episodes(self, episodes: List[Dict[str, str]], series_name: str, series_config: Dict) -> int:
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

            result = subprocess.run(cmd, capture_output=False, text=True)

            if result.returncode == 0:
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
            self.logger.info(f"Filtered to {len(episodes_to_download)} episode(s) (excluded {excluded_count})")

        self.logger.info("\nEpisodes to download:")
        for i, ep in enumerate(episodes_to_download, 1):
            print(f"  {i}. {ep['title']}")

        # Download episodes (yt-dlp will handle duplicate detection)
        return self.download_episodes(episodes_to_download, series_name, series)

    def run(self):
        """Main execution method"""
        print("TVer Auto Downloader")
        print("=" * 60)

        if self.debug:
            self.logger.info("DEBUG MODE ENABLED")

        # Check VPN
        if not self.check_vpn_connection():
            print("\nExiting...")
            return

        # Get enabled series
        enabled_series = [s for s in self.config.get("series", []) if s.get("enabled", True)]

        if not enabled_series:
            self.logger.warning("\nNo enabled series in config.json")
            return

        self.logger.info(f"\nProcessing {len(enabled_series)} series...")

        total_downloaded = 0
        for series in enabled_series:
            try:
                count = self.process_series(series)
                total_downloaded += count
            except Exception as e:
                self.logger.error(f"Error processing {series.get('name', 'Unknown')}: {e}", exc_info=self.debug)
                continue

        print(f"\n{'=' * 60}")
        self.logger.info(f"Complete! Processed {total_downloaded} episode(s)")
        print(f"{'=' * 60}")


def main():
    # Check for debug flag in command line
    debug = "--debug" in sys.argv or "-d" in sys.argv
    downloader = TVerDownloader(debug=debug)
    downloader.run()


if __name__ == "__main__":
    main()
