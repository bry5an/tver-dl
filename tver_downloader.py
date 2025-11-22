#!/usr/bin/env python3
"""
TVer Auto Downloader
Downloads new episodes from TVer series pages using yt-dlp
"""

import argparse
import json
import logging
import os
import subprocess
import threading
import requests
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# --- Components ---

class ConfigManager:
    """Handles configuration loading, validation, and defaults."""
    
    DEFAULT_CONFIG = {
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
            "--write-subs"
        ],
    }

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)

    def load(self) -> Dict[str, Any]:
        """Load configuration from file, creating default if missing."""
        if not self.config_path.exists():
            self._create_default_config()
            return self.DEFAULT_CONFIG

        try:
            config = yaml.safe_load(self.config_path.read_text()) or {}
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.DEFAULT_CONFIG

        # Expand environment variables in download_path
        if "download_path" in config:
            config["download_path"] = os.path.expandvars(config["download_path"])
            
        return config

    def _create_default_config(self):
        """Create a default configuration file."""
        self.config_path.write_text(
            yaml.dump(self.DEFAULT_CONFIG, allow_unicode=True, default_flow_style=False)
        )
        print(f"Created default config at {self.config_path}")
        print("Please edit the config file to add your series URLs")


class VPNChecker:
    """Verifies VPN connection to Japan."""
    
    SERVICES = [
        ("https://ipapi.co/json/", lambda r: r.json().get("country_code")),
        ("https://ip.seeip.org/geoip", lambda r: r.json().get("country_code")),
        ("https://api.myip.com", lambda r: r.json().get("cc")),
    ]

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def check(self) -> bool:
        """Check if connected to a VPN (trying multiple IP geolocation services in parallel)."""
        self.logger.info("Checking VPN connection...")
        
        connected = False
        details = "Unknown"

        def check_service(url, parser):
            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                country = parser(response)
                ip = response.json().get("ip", "unknown")
                return country, ip
            except Exception:
                return None, None

        with ThreadPoolExecutor(max_workers=len(self.SERVICES)) as executor:
            futures = [executor.submit(check_service, url, parser) for url, parser in self.SERVICES]
            
            for future in as_completed(futures):
                country, ip = future.result()
                if country:
                    if country == "JP":
                        self.logger.info(f"✓ Connected via Japan IP ({ip})")
                        return True
                    details = f"Country: {country}, IP: {ip}"

        # If we get here, no service confirmed JP
        self.logger.warning(f"Not connected to Japan VPN (Last detected: {details})")
        print("  TVer downloads may fail without Japanese IP")
        response = input("Continue anyway? (y/n): ")
        return response.lower() == "y"


class EpisodeFilter:
    """Filters episodes based on include/exclude patterns."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def should_download(self, title: str, series_config: Dict) -> bool:
        """Check if episode should be downloaded based on series-specific filters."""
        include_patterns = series_config.get("include_patterns", [])
        exclude_patterns = series_config.get("exclude_patterns", [])

        if not include_patterns and not exclude_patterns:
            self.logger.debug(f"  No filters configured, including: {title}")
            return True

        self.logger.debug(f"Checking episode: {title}")

        # Check exclude patterns
        for pattern in exclude_patterns:
            if pattern in title:
                self.logger.debug(f"  -> Excluded (matched exclude pattern '{pattern}')")
                return False

        # Check include patterns
        if include_patterns:
            for pattern in include_patterns:
                if pattern in title:
                    self.logger.debug(f"  -> Included (matched include pattern '{pattern}')")
                    return True
            self.logger.debug("  -> Excluded (no include pattern matched)")
            return False

        self.logger.debug("  -> Included (passed all filters)")
        return True


class YtDlpHandler:
    """Handles interactions with yt-dlp for extraction and downloading."""

    def __init__(self, config: Dict, logger: logging.Logger, debug: bool = False, subtitles_only: bool = False):
        self.config = config
        self.logger = logger
        self.debug = debug
        self.subtitles_only = subtitles_only
        self.extract_lock = threading.Lock()
        self.download_report = {}

    def extract_episodes(self, series_url: str) -> List[Dict[str, str]]:
        """Use yt-dlp to extract episode URLs from a series page."""
        try:
            self.logger.info(f"Using yt-dlp to extract episodes from: {series_url}")
            
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--print", "%(id)s|%(title)s|%(webpage_url)s",
                "--no-warnings",
                "--playlist-items", "1-10",
                series_url,
            ]

            self.logger.debug(f"Running command: {' '.join(cmd)}")

            # Serialize extraction calls
            with self.extract_lock:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                self.logger.error(f"yt-dlp extraction failed: {result.stderr}")
                return []

            episodes = []
            for line in result.stdout.strip().splitlines():
                if not line or "|" not in line:
                    continue
                
                parts = line.split("|", 2)
                if len(parts) >= 3:
                    episodes.append({
                        "id": parts[0],
                        "title": parts[1],
                        "url": parts[2]
                    })
                    self.logger.debug(f"Found episode: {parts[1]} - {parts[2]}")

            self.logger.info(f"yt-dlp found {len(episodes)} episode(s)")
            return episodes

        except Exception as e:
            self.logger.error(f"Error extracting episodes: {e}", exc_info=self.debug)
            return []

    def download(self, episodes: List[Dict[str, str]], series_name: str) -> int:
        """Download episodes using yt-dlp."""
        if not episodes:
            return 0

        try:
            download_path = self.config.get("download_path", "./downloads")
            Path(download_path).mkdir(parents=True, exist_ok=True)
            
            archive_file = self.config.get("archive_file", "downloaded.txt")
            archive_path = Path(download_path) / archive_file

            # Filter for subtitles only if requested
            episode_urls = self._prepare_download_list(episodes, download_path)
            if not episode_urls:
                self.logger.info("No episodes need downloading (subtitles check passed).")
                return 0

            cmd = self._build_download_command(episode_urls, download_path, archive_path)
            
            self.logger.info(f"Downloading {len(episodes)} episode(s)...")
            if series_name not in self.download_report:
                self.download_report[series_name] = {"success": [], "missing_subtitles": []}

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self._process_download_results(result.stdout, download_path, series_name, episodes)
                self.logger.info("✓ Download process completed")
                return len(episodes)
            else:
                self.logger.error(f"✗ Download failed: {result.stderr}")
                return 0

        except Exception as e:
            self.logger.error(f"✗ Download error: {e}", exc_info=self.debug)
            return 0

    def _prepare_download_list(self, episodes: List[Dict], download_path: str) -> List[str]:
        """Prepare list of URLs, filtering for missing subtitles if needed."""
        if not self.subtitles_only:
            return [ep["url"] for ep in episodes]

        download_dir = Path(download_path)
        urls = []
        for ep in episodes:
            if not self._has_subtitle(download_dir, ep["title"]):
                urls.append(ep["url"])
        return urls

    def _build_download_command(self, urls: List[str], download_path: str, archive_path: Path) -> List[str]:
        """Build the yt-dlp command based on configuration."""
        base_options = list(self.config.get("yt_dlp_options", []))

        if self.subtitles_only:
            # Filter out output templates and ensure subtitle options
            base_options = [opt for opt in base_options if opt not in ("-o", "--output")]
            if "--skip-download" not in base_options:
                base_options.insert(0, "--skip-download")
            if "--write-subs" not in base_options:
                base_options.append("--write-subs")
            # Ensure Japanese subs
            if "--sub-lang" in base_options:
                idx = base_options.index("--sub-lang")
                if idx + 1 < len(base_options):
                    base_options.pop(idx)
                    base_options.pop(idx)
            base_options.extend(["--sub-lang", "ja"])

        cmd = [
            "yt-dlp",
            "--download-archive", str(archive_path),
            *base_options,
            "-P", download_path,
            *urls
        ]
        
        if self.debug:
            cmd.append("-v")
            
        return cmd

    def _process_download_results(self, stdout: str, download_path: str, series_name: str, episodes: List[Dict]):
        """Parse output and check for subtitles."""
        for line in stdout.splitlines():
            if "[download] Destination:" in line:
                file_path = line.split("Destination: ")[-1].strip()
                self.download_report[series_name]["success"].append(Path(file_path).stem)

        # Check for missing subtitles
        download_dir = Path(download_path)
        for ep in episodes:
            if not self._has_subtitle(download_dir, ep["title"]):
                self.logger.warning(f"Missing subtitle for: {ep['title']}")
                self.download_report[series_name]["missing_subtitles"].append(ep["title"])

    def _has_subtitle(self, download_dir: Path, title: str) -> bool:
        """Check if any subtitle file exists for the title."""
        for ext in ["vtt", "srt", "ass"]:
            if list(download_dir.glob(f"**/{title}*.{ext}")):
                return True
        return False


# --- Main Application ---

class TVerDownloader:
    """Main application controller."""

    def __init__(self, config_path: str = "config.json", debug: bool = False, subtitles_only: bool = False):
        self.debug = debug
        self.subtitles_only = subtitles_only
        
        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S"
        )
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load()
        
        # Override debug/subtitles from config if not set in args
        self.debug = self.debug or self.config.get("debug", False)
        self.subtitles_only = self.subtitles_only or self.config.get("subtitles_only", False)
        
        self.vpn_checker = VPNChecker(self.logger)
        self.filter = EpisodeFilter(self.logger)
        self.ytdlp = YtDlpHandler(self.config, self.logger, self.debug, self.subtitles_only)

    def run(self, skip_vpn_check: bool = False, max_workers: int = 3):
        """Execute the main download workflow."""
        print("TVer Auto Downloader")
        print("=" * 60)

        if not skip_vpn_check and not self.vpn_checker.check():
            print("\nExiting...")
            return

        enabled_series = [s for s in self.config.get("series", []) if s.get("enabled", True)]
        if not enabled_series:
            self.logger.warning("No enabled series found in config.")
            return

        self.logger.info(f"Processing {len(enabled_series)} series with {max_workers} workers...")
        
        total_downloaded = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._process_series, s): s for s in enabled_series}
            for future in as_completed(futures):
                try:
                    total_downloaded += future.result()
                except Exception as e:
                    series_name = futures[future].get('name', 'Unknown')
                    self.logger.error(f"Error processing {series_name}: {e}", exc_info=self.debug)

        self._print_summary()
        print(f"\n{'=' * 60}")
        self.logger.info(f"Complete! Processed {total_downloaded} episode(s)")
        print(f"{'=' * 60}")

    def _process_series(self, series: Dict) -> int:
        """Process a single series."""
        series_name = series["name"]
        series_url = series["url"]

        print(f"\n{'=' * 60}\nProcessing: {series_name}\n{'=' * 60}")

        # 1. Extract
        all_episodes = self.ytdlp.extract_episodes(series_url)
        if not all_episodes:
            return 0

        # 2. Filter
        episodes_to_download = [
            ep for ep in all_episodes 
            if self.filter.should_download(ep["title"], series)
        ]

        if not episodes_to_download:
            self.logger.info("No episodes match filter criteria.")
            return 0

        # 3. Check Archive (deduplicate)
        new_episodes = self._filter_archived(episodes_to_download)
        if not new_episodes:
            self.logger.info("All matching episodes already downloaded.")
            return 0

        # 4. Download
        self.logger.info(f"Downloading {len(new_episodes)} new episode(s)...")
        return self.ytdlp.download(new_episodes, series_name)

    def _filter_archived(self, episodes: List[Dict]) -> List[Dict]:
        """Filter out episodes that are already in the download archive."""
        archive_path = Path(self.config.get("download_path", "./downloads")) / self.config.get("archive_file", "downloaded.txt")
        if not archive_path.exists():
            return episodes
            
        downloaded_urls = set(archive_path.read_text().splitlines())
        return [ep for ep in episodes if ep["url"] not in downloaded_urls]

    def _print_summary(self):
        """Print the final download report."""
        report = self.ytdlp.download_report
        if not any(r.get("success") for r in report.values()):
            print("\nNo new episodes were downloaded.")
            return

        print("\nDownload Summary")
        print("=" * 60)
        for series_name, data in report.items():
            success = data.get("success", [])
            missing = data.get("missing_subtitles", [])
            
            if success:
                print(f"\n{series_name} ({len(success)} downloaded):")
                for title in success:
                    print(f"  ✓ {title}")
                
                if missing:
                    print(f"  ⚠ Missing subtitles ({len(missing)}):")
                    for title in missing:
                        print(f"    - {title}")


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

    config_path = args.config
    if not config_path:
        config_path = "config.yaml" if Path("config.yaml").exists() else "config.json"

    downloader = TVerDownloader(
        config_path=config_path,
        debug=args.debug,
        subtitles_only=args.subtitles_only,
    )
    downloader.run(skip_vpn_check=args.skip_vpn_check, max_workers=args.max_workers)


if __name__ == "__main__":
    main()
