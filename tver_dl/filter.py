import logging
from typing import Dict

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
