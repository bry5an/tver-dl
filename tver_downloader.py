#!/usr/bin/env python3
"""
TVer Auto Downloader
Downloads new episodes from TVer series pages using yt-dlp
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
import re
import logging

# Try to import required packages
try:
    import requests
except ImportError:
    print("Installing required packages with uv...")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests


class TVerDownloader:
    def __init__(self, config_path: str = "config.json", history_path: str = "downloaded.json", debug: bool = False):
        self.config_path = Path(config_path)
        self.history_path = Path(history_path)
        self.config = self.load_config()
        self.history = self.load_history()
        self.debug = debug or self.config.get("debug", False)
        
        # Setup logging
        log_level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self) -> Dict:
        """Load configuration file"""
        if not self.config_path.exists():
            default_config = {
                "series": [
                    {
                        "name": "Example Series",
                        "url": "https://tver.jp/series/...",
                        "enabled": True
                    }
                ],
                "download_path": "./downloads",
                "debug": False,
                "filter_episodes": True,
                "exclude_patterns": [
                    "予告",
                    "ダイジェスト",
                    "解説放送版",
                    "インタビュー",
                    "メイキング",
                    "特報",
                    "みどころ",
                    "SP"
                ],
                "yt_dlp_options": [
                    "-o", "%(series)s/%(title)s.%(ext)s",
                    "--write-sub",
                    "--sub-lang", "ja"
                ]
            }
            self.config_path.write_text(json.dumps(default_config, indent=2, ensure_ascii=False))
            print(f"Created default config at {self.config_path}")
            print("Please edit the config file to add your series URLs")
            return default_config
        
        return json.loads(self.config_path.read_text())
    
    def load_history(self) -> Dict[str, Set[str]]:
        """Load download history"""
        if not self.history_path.exists():
            return {}
        
        data = json.loads(self.history_path.read_text())
        # Convert lists back to sets
        return {k: set(v) for k, v in data.items()}
    
    def save_history(self):
        """Save download history"""
        # Convert sets to lists for JSON serialization
        data = {k: list(v) for k, v in self.history.items()}
        self.history_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def check_vpn_connection(self) -> bool:
        """Check if connected to a VPN (basic check via IP geolocation)"""
        try:
            self.logger.info("Checking VPN connection...")
            response = requests.get("https://ipapi.co/json/", timeout=10)
            data = response.json()
            country = data.get("country_code", "")
            
            if country == "JP":
                self.logger.info(f"✓ Connected via Japan IP ({data.get('ip')})")
                return True
            else:
                self.logger.warning(f"Not connected to Japan VPN (detected: {country})")
                print("  TVer downloads may fail without Japanese IP")
                response = input("Continue anyway? (y/n): ")
                return response.lower() == 'y'
        except Exception as e:
            self.logger.error(f"Could not verify VPN status: {e}")
            response = input("Continue anyway? (y/n): ")
            return response.lower() == 'y'
    
    def should_download_episode(self, title: str) -> bool:
        """Check if episode should be downloaded based on filters"""
        if not self.config.get("filter_episodes", False):
            return True
        
        self.logger.debug(f"Checking episode: {title}")
        
        # First, check exclude patterns (previews, digests, audio description, etc.)
        # This catches things like "＃1【解説放送版】" or "【予告】" before we check episode numbers
        exclude_patterns = self.config.get("exclude_patterns", [])
        
        for pattern in exclude_patterns:
            if pattern in title:
                self.logger.debug(f"  -> Excluded (matched pattern '{pattern}')")
                return False
        
        # Now check if it has an episode number
        # Matches: ＃1, ＃2, 第1話, 第2話, #1, #2, etc.
        episode_patterns = [
            r'[＃#]\d+',         # ＃1, #1 (no space between symbol and number)
            r'[＃#]\s+\d+',      # ＃ 1, # 1 (with space)
            r'第\d+話',          # 第1話
            r'第\s+\d+\s+話',    # 第 1 話 (with spaces)
        ]
        
        has_episode_number = any(re.search(pattern, title) for pattern in episode_patterns)
        
        if has_episode_number:
            self.logger.debug(f"  -> Included (main episode)")
            return True
        else:
            self.logger.debug(f"  -> Excluded (no episode number)")
            return False
    
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
                series_url
            ]
            
            self.logger.debug(f"Running command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                self.logger.error(f"yt-dlp extraction failed: {result.stderr}")
                return []
            
            episodes = []
            # Each line is a JSON object for an episode
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    episode_url = data.get('url') or data.get('webpage_url') or data.get('id')
                    
                    # Make sure we have a full URL
                    if episode_url and not episode_url.startswith('http'):
                        episode_url = f"https://tver.jp/episodes/{episode_url}"
                    
                    title = data.get('title', episode_url)
                    
                    if episode_url:
                        episodes.append({
                            'url': episode_url,
                            'title': title,
                            'id': data.get('id', '')
                        })
                        self.logger.debug(f"Found episode: {title} - {episode_url}")
                        
                except json.JSONDecodeError as e:
                    self.logger.debug(f"Could not parse JSON line: {line[:100]}... Error: {e}")
                    continue
            
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
            match = re.search(r'/series/([^/]+)', series_url)
            if not match:
                self.logger.warning("Could not extract series ID from URL")
                return []
            
            series_id = match.group(1)
            self.logger.info(f"Attempting to fetch episodes via API for series: {series_id}")
            
            # TVer API endpoint (may need adjustment)
            api_url = f"https://platform-api.tver.jp/service/api/v1/callSeriesEpisodes/{series_id}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Origin': 'https://tver.jp',
                'Referer': series_url
            }
            
            self.logger.debug(f"API request URL: {api_url}")
            response = requests.get(api_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            self.logger.debug(f"API response keys: {data.keys()}")
            
            episodes = []
            # Parse API response (structure may vary)
            episode_list = data.get('result', {}).get('contents', [])
            
            for ep in episode_list:
                episode_id = ep.get('id') or ep.get('content', {}).get('id')
                if episode_id:
                    episode_url = f"https://tver.jp/episodes/{episode_id}"
                    title = ep.get('title') or ep.get('content', {}).get('title', episode_id)
                    
                    episodes.append({
                        'url': episode_url,
                        'title': title,
                        'id': episode_id
                    })
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
        
        # Filter episodes based on config
        if self.config.get("filter_episodes", False):
            self.logger.info(f"Filtering episodes (found {len(episodes)} total)...")
            filtered_episodes = [ep for ep in episodes if self.should_download_episode(ep['title'])]
            excluded_count = len(episodes) - len(filtered_episodes)
            if excluded_count > 0:
                self.logger.info(f"Excluded {excluded_count} non-episode content (previews, digests, etc.)")
            episodes = filtered_episodes
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_episodes = []
        for ep in episodes:
            if ep['url'] not in seen_urls:
                seen_urls.add(ep['url'])
                unique_episodes.append(ep)
        
        if not unique_episodes:
            self.logger.warning("No episodes found using any method")
            self.logger.info("You can try manually adding episode URLs to download in the config")
        
        return unique_episodes
    
    def download_episode(self, episode_url: str, series_name: str) -> bool:
        """Download an episode using yt-dlp"""
        try:
            download_path = self.config.get("download_path", "./downloads")
            Path(download_path).mkdir(parents=True, exist_ok=True)
            
            # Build yt-dlp command
            cmd = [
                "yt-dlp",
                *self.config.get("yt_dlp_options", []),
                "-P", download_path,
                episode_url
            ]
            
            if self.debug:
                cmd.append("-v")  # Verbose output in debug mode
            
            self.logger.debug(f"Download command: {' '.join(cmd)}")
            self.logger.info(f"  Downloading with yt-dlp...")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if self.debug:
                self.logger.debug(f"yt-dlp stdout: {result.stdout}")
                self.logger.debug(f"yt-dlp stderr: {result.stderr}")
            
            if result.returncode == 0:
                self.logger.info(f"  ✓ Download successful")
                return True
            else:
                self.logger.error(f"  ✗ Download failed")
                if not self.debug:
                    self.logger.error(f"  Error: {result.stderr[:200]}")
                    self.logger.info("  Run with debug=true in config.json for more details")
                return False
                
        except FileNotFoundError:
            self.logger.error("  ✗ Error: yt-dlp not found. Please install it:")
            self.logger.error("    brew install yt-dlp")
            return False
        except Exception as e:
            self.logger.error(f"  ✗ Download error: {e}", exc_info=self.debug)
            return False
    
    def process_series(self, series: Dict) -> int:
        """Process a single series and download new episodes"""
        series_name = series['name']
        series_url = series['url']
        
        print(f"\n{'='*60}")
        self.logger.info(f"Processing: {series_name}")
        self.logger.info(f"URL: {series_url}")
        print(f"{'='*60}")
        
        # Get episodes from series page
        episodes = self.get_episode_urls(series_url)
        
        if not episodes:
            self.logger.warning("No episodes found on series page")
            return 0
        
        self.logger.info(f"Found {len(episodes)} episode(s)")
        
        # Check which episodes are new
        if series_name not in self.history:
            self.history[series_name] = set()
        
        new_episodes = [ep for ep in episodes if ep['url'] not in self.history[series_name]]
        
        if not new_episodes:
            self.logger.info("No new episodes to download")
            return 0
        
        self.logger.info(f"\n{len(new_episodes)} new episode(s) to download:")
        for i, ep in enumerate(new_episodes, 1):
            print(f"  {i}. {ep['title']}")
        
        # Download new episodes
        downloaded_count = 0
        for ep in new_episodes:
            print(f"\nDownloading: {ep['title']}")
            self.logger.info(f"  URL: {ep['url']}")
            
            if self.download_episode(ep['url'], series_name):
                self.history[series_name].add(ep['url'])
                downloaded_count += 1
                self.save_history()  # Save after each successful download
        
        return downloaded_count
    
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
        enabled_series = [s for s in self.config.get('series', []) if s.get('enabled', True)]
        
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
        
        print(f"\n{'='*60}")
        self.logger.info(f"Complete! Downloaded {total_downloaded} new episode(s)")
        print(f"{'='*60}")


def main():
    # Check for debug flag in command line
    debug = "--debug" in sys.argv or "-d" in sys.argv
    downloader = TVerDownloader(debug=debug)
    downloader.run()


if __name__ == "__main__":
    main()