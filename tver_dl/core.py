import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List
import re

from rich.logging import RichHandler

from .config import ConfigManager
from .vpn import VPNChecker
from .filter import EpisodeFilter
from .ytdlp import YtDlpHandler
from .display import DisplayManager
from .tracker import CSVTracker, DatabaseTracker
from .tver_api import TVerClient

class TVerDownloader:
    """Main application controller."""

    def __init__(self, config_path: str = None, debug: bool = False, subtitles_only: bool = False):
        self.debug = debug
        self.subtitles_only = subtitles_only
        
        # Initialize display first to get the shared console
        self.display = DisplayManager()
        
        # Setup logging to use RichHandler with the shared console
        # This ensures logs don't break the progress bar display
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=self.display.console, rich_tracebacks=True, show_path=False)],
            force=True
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
        self.api = TVerClient(self.logger)
        
        # History Tracker Initialization
        history_config = self.config.get("history", {})
        if history_config.get("type", "csv") == "database":
            db_url = history_config.get("db_connection_string")
            if not db_url:
                raise ValueError("Database connection string missing in config.")
            self.tracker = DatabaseTracker(db_url, self.logger)
        else:
            # Fallback to CSV
            download_path = self.config.get("download_path", "./downloads")
            csv_path = history_config.get("csv_path", "history.csv")
            history_file = Path(download_path) / csv_path
            self.tracker = CSVTracker(history_file, self.logger)

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
        
        # Start the rich progress display
        with self.display.start():
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._process_series, s): s for s in enabled_series}
                for future in as_completed(futures):
                    try:
                        total_downloaded += future.result()
                    except Exception as e:
                        series_name = futures[future].get('name', 'Unknown')
                        self.display.log(f"Error processing {series_name}: {e}", style="bold red")

        self._print_summary()
        print(f"\n{'=' * 60}")
        self.logger.info(f"Complete! Processed {total_downloaded} episode(s)")
        print(f"{'=' * 60}")

    def _process_series(self, series: Dict) -> int:
        """Process a single series."""
        series_name = series["name"]
        series_url = series["url"]

        # Create a task for this series
        task_id = self.display.add_series_task(series_name)
        self.display.start_task(task_id)

        # 1. Extract
        self.display.update_status(task_id, "Extracting...")
        
        # Extract series ID from URL
        match = re.search(r'series/([a-zA-Z0-9]+)', series_url)
        if not match:
            self.logger.error(f"Could not parse series ID from URL: {series_url}")
            self.display.update_status(task_id, "[red]Invalid URL")
            return 0
            
        series_id = match.group(1)
        all_episodes = self.api.get_series_episodes(series_id, series_name)
        
        if not all_episodes:
            self.display.update_status(task_id, "[red]No episodes found")
            return 0

        # 2. Filter
        episodes_to_download = [
            ep for ep in all_episodes 
            if self.filter.should_download(ep["title"], series)
        ]

        if not episodes_to_download:
            self.display.update_status(task_id, "[yellow]Filtered out")
            return 0

        # 3. Check Archive (deduplicate via Tracker)
        new_episodes = self._filter_archived(episodes_to_download)
        if not new_episodes:
            self.display.update_status(task_id, "[green]Up to date")
            self.display.update_progress(task_id, total=1, advance=1) # Mark done
            return 0

        # 4. Download
        self.display.update_status(task_id, f"Downloading {len(new_episodes)} eps...")
        self.display.update_progress(task_id, total=len(new_episodes))
        
        # Pass display callback to ytdlp
        # Callback receives absolute progress (e.g. 1.5 for 1.5 episodes done)
        def progress_callback(progress):
            self.display.update_progress(task_id, completed=progress)

        results = self.ytdlp.download(new_episodes, series_name, progress_callback)
        
        # Update Tracker
        for item in results:
            self.tracker.add_download(
                series_info={"name": item["series_name"], "url": series_url}, 
                episode_info={
                    "title": item["episode_name"], 
                    "url": item["url"], 
                    "episode_number": item["episode_number"]
                },
                download_info={
                    "filepath": item["filepath"],
                    "subtitles": item["subtitles"]
                }
            )
        
        self.display.update_status(task_id, "[green]Done")
        return len(results)

    def _filter_archived(self, episodes: List[Dict]) -> List[Dict]:
        """Filter out episodes that are already in the history."""
        return [ep for ep in episodes if not self.tracker.has_episode(ep["url"])]

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
