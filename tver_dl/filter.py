import logging
from typing import Dict

class EpisodeFilter:
    """Filters episodes based on include/exclude patterns."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def should_download(self, episode: Dict, series_config: Dict) -> bool:
        """Check if episode should be downloaded based on series-specific filters."""
        title = episode.get("title", "")
        season_name = episode.get("season_name", "")
        
        include_patterns = series_config.get("include_patterns", [])
        exclude_patterns = series_config.get("exclude_patterns", [])
        target_seasons = series_config.get("target_seasons", [])

        # 1. Season Filtering (Priority)
        if target_seasons:
            if season_name in target_seasons:
                self.logger.debug(f"  -> Included (season '{season_name}' matches target)")
                return True
            else:
                self.logger.debug(f"  -> Excluded (season '{season_name}' not in targets)")
                return False

        # If no patterns configured at all, check if we might want to default to "本編"?
        # For now, keep existing behavior: if no filters, download everything.
        if not include_patterns and not exclude_patterns:
            self.logger.debug(f"  No filters configured, including: {title}")
            return True

        self.logger.debug(f"Checking episode: {title} (Season: {season_name})")

        # 2. Exclude Patterns
        for pattern in exclude_patterns:
            if pattern in title:
                self.logger.debug(f"  -> Excluded (matched exclude pattern '{pattern}')")
                return False

        # 3. Include Patterns
        if include_patterns:
            for pattern in include_patterns:
                if pattern in title:
                    self.logger.debug(f"  -> Included (matched include pattern '{pattern}')")
                    return True
            self.logger.debug("  -> Excluded (no include pattern matched)")
            return False

        self.logger.debug("  -> Included (passed all filters)")
        return True
