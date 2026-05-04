import csv
import logging
from pathlib import Path
from typing import Optional

class HistoryManager:
    """Manages the download history using a CSV file."""

    FIELDNAMES = ["series_name", "episode_name", "url", "episode_number", "subtitles"]

    def __init__(self, history_file: Path):
        self.history_file = Path(history_file)
        self.logger = logging.getLogger(__name__)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Create the CSV file with headers if it doesn't exist."""
        if not self.history_file.exists():
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writeheader()

    def has_episode(self, url: str) -> bool:
        """Check if an episode URL is already in the history."""
        if not self.history_file.exists():
            return False
        
        try:
            with open(self.history_file, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["url"] == url:
                        return True
        except Exception as e:
            self.logger.error(f"Error reading history file: {e}")
        
        return False

    def add_entry(self, series_name: str, episode_name: str, url: str, 
                  episode_number: Optional[str], subtitles: bool):
        """Add a new entry to the history."""
        try:
            with open(self.history_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writerow({
                    "series_name": series_name,
                    "episode_name": episode_name,
                    "url": url,
                    "episode_number": episode_number or "",
                    "subtitles": str(subtitles)
                })
        except Exception as e:
            self.logger.error(f"Error writing to history file: {e}")
