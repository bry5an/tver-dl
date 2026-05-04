import os
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

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
        "archive_file": "downloaded.txt", # Legacy/fallback
        "history": {
            "type": "csv",
            "csv_path": "history.csv",
            "db_connection_string": "postgresql://user:pass@host:5432/db"
        },
        "debug": False,
        "yt_dlp_options": [
            "-o",
            "%(series)s/%(title)s.%(ext)s",
            "--write-subs"
        ],
    }

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self._get_default_config_path()

    def _get_default_config_path(self) -> Path:
        """Determine the platform-specific default config path."""
        app_name = "tver-dl"
        filename = "config.yaml"

        if sys.platform == "win32":
            base_path = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            # Linux/Mac (XDG standard)
            base_path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        
        return base_path / app_name / filename

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

        # Parse and normalize series
        raw_series = config.get("series", [])
        normalized_series = []
        
        if isinstance(raw_series, list):
            # Legacy format or simple list
            for s in raw_series:
                if isinstance(s, dict):
                    self._apply_series_defaults(s)
                    normalized_series.append(s)
        elif isinstance(raw_series, dict):
            # Categorized format
            for category_name, series_list in raw_series.items():
                if isinstance(series_list, list):
                    for s in series_list:
                        if isinstance(s, dict):
                            s["category"] = category_name
                            self._apply_series_defaults(s)
                            normalized_series.append(s)
                            
        config["series"] = normalized_series

        # Expand environment variables in download_path
        if "download_path" in config:
            config["download_path"] = os.path.expandvars(config["download_path"])

        # Expand environment variables in db_connection_string
        if "history" in config and isinstance(config["history"], dict):
            if "db_connection_string" in config["history"]:
                config["history"]["db_connection_string"] = os.path.expandvars(config["history"]["db_connection_string"])
            
        return config

    def _apply_series_defaults(self, series: Dict):
        """Apply default values to a series configuration."""
        series.setdefault("enabled", True)
        series.setdefault("target_seasons", ["本編"])
        series.setdefault("subtitles", True)

    def _create_default_config(self):
        """Create a default configuration file."""
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.config_path.write_text(
            yaml.dump(self.DEFAULT_CONFIG, allow_unicode=True, default_flow_style=False)
        )
        print(f"Created default config at {self.config_path}")
        print("Please edit the config file to add your series URLs")
