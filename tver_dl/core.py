import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List

from .config import ConfigManager
from .vpn import VPNChecker
from .filter import EpisodeFilter
from .ytdlp import YtDlpHandler

class TVerDownloader:
    """Main application controller."""

    def __init__(self, config_path: str = None, debug: bool = False, subtitles_only: bool = False):
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
