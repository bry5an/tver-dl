import csv
import logging
import os
import socket
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    psycopg2 = None

class BaseTracker(ABC):
    """Abstract base class for download tracking."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.hostname = socket.gethostname()

    @abstractmethod
    def has_episode(self, url: str) -> bool:
        """Check if an episode URL is already in the history."""
        pass

    @abstractmethod
    def add_download(self, series_info: Dict, episode_info: Dict, download_info: Dict):
        """Record a successful download."""
        pass

class CSVTracker(BaseTracker):
    """Manages history using a CSV file (replaces HistoryManager)."""
    
    FIELDNAMES = ["series_name", "episode_name", "url", "episode_number", "subtitles"]

    def __init__(self, history_file: Path, logger: logging.Logger):
        super().__init__(logger)
        self.history_file = Path(history_file)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not self.history_file.exists():
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writeheader()

    def has_episode(self, url: str) -> bool:
        if not self.history_file.exists():
            return False
        try:
            with open(self.history_file, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["url"] == url:
                        return True
        except Exception as e:
            self.logger.error(f"Error reading CSV history: {e}")
        return False

    def add_download(self, series_info: Dict, episode_info: Dict, download_info: Dict):
        try:
            with open(self.history_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writerow({
                    "series_name": series_info["name"],
                    "episode_name": episode_info["title"],
                    "url": episode_info["url"],
                    "episode_number": episode_info.get("episode_number") or "",
                    "subtitles": str(download_info.get("subtitles", False))
                })
        except Exception as e:
            self.logger.error(f"Error writing to CSV history: {e}")

class DatabaseTracker(BaseTracker):
    """Manages history using a PostgreSQL database."""

    def __init__(self, connection_string: str, logger: logging.Logger):
        super().__init__(logger)
        self.connection_string = connection_string
        if not psycopg2:
            raise ImportError("psycopg2-binary is required for database tracking.")

    def _get_connection(self):
        try:
            return psycopg2.connect(self.connection_string)
        except Exception as e:
            if "No route to host" in str(e) and "supabase" in self.connection_string:
                self.logger.error("Connection failed. If using Supabase, ensure you are using the Connection Pooler URL (IPv4 compliant) or have IPv6 support.")
            raise e

    def has_episode(self, url: str) -> bool:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Check if episode exists and has a successful download
                    query = """
                        SELECT 1 FROM downloads d
                        JOIN episodes e ON d.episode_id = e.id
                        WHERE e.episode_url = %s AND d.status = 'downloaded'
                    """
                    cur.execute(query, (url,))
                    return cur.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Error checking DB history: {e}")
            return False

    def _extract_series_id(self, url: str) -> str:
        """Extract series ID from URL safely."""
        match = re.search(r'series/([a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        # Fallback for unexpected formats
        return url.rstrip('/').split("/")[-1]

    def add_download(self, series_info: Dict, episode_info: Dict, download_info: Dict):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. UPSERT Series
                    series_url = series_info["url"]
                    tver_series_id = self._extract_series_id(series_url)
                    has_subtitles = download_info.get("subtitles", False)
                    
                    # Update has_subtitles if we found subtitles, otherwise leave it (it might be True from other eps)
                    # If it's the first time and has_subtitles is False, it will stay Null or False depending on default
                    if has_subtitles:
                        cur.execute("""
                            INSERT INTO series (tver_series_id, name, url, has_subtitles)
                            VALUES (%s, %s, %s, TRUE)
                            ON CONFLICT (tver_series_id) DO UPDATE 
                            SET updated_at = now(), has_subtitles = TRUE
                            RETURNING id
                        """, (tver_series_id, series_info["name"], series_url))
                    else:
                        cur.execute("""
                            INSERT INTO series (tver_series_id, name, url)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (tver_series_id) DO UPDATE 
                            SET updated_at = now()
                            RETURNING id
                        """, (tver_series_id, series_info["name"], series_url))
                    
                    series_id = cur.fetchone()[0]

                    # 2. UPSERT Episode
                    ep_url = episode_info["url"]
                    tver_episode_id = ep_url.split("/")[-1] if "/episodes/" in ep_url else "unknown_" + ep_url[-10:]
                    
                    ep_num = episode_info.get("episode_number")
                    if ep_num == "NA": ep_num = None
                    try:
                        ep_num = int(ep_num) if ep_num else None
                    except ValueError:
                        ep_num = None

                    cur.execute("""
                        INSERT INTO episodes (series_id, tver_episode_id, title, episode_number, episode_url, subtitles_checked_at)
                        VALUES (%s, %s, %s, %s, %s, now())
                        ON CONFLICT (tver_episode_id) DO UPDATE
                        SET title = EXCLUDED.title, subtitles_checked_at = now()
                        RETURNING id
                    """, (series_id, tver_episode_id, episode_info["title"], ep_num, ep_url))
                    episode_id = cur.fetchone()[0]

                    # 3. INSERT Download
                    file_path = download_info.get("filepath")
                    file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0
                    
                    cur.execute("""
                        INSERT INTO downloads (
                            episode_id, status, downloaded_at, file_path, 
                            file_size_bytes, downloader_host
                        )
                        VALUES (%s, 'downloaded', now(), %s, %s, %s)
                        ON CONFLICT (episode_id) DO UPDATE
                        SET status = 'downloaded', downloaded_at = now()
                    """, (episode_id, file_path, file_size, self.hostname))

                    # 4. INSERT/UPDATE Subtitles
                    sub_status = 'downloaded' if has_subtitles else 'missing'
                    subtitle_format = download_info.get("subtitle_format")
                    
                    cur.execute("""
                        INSERT INTO subtitles (
                            episode_id, status, checked_at, downloaded_at,
                            subtitle_format, series_name, episode_title
                        )
                        VALUES (%s, %s, now(), %s, %s, %s, %s)
                        ON CONFLICT (episode_id) DO UPDATE
                        SET status = EXCLUDED.status, 
                            checked_at = now(),
                            downloaded_at = COALESCE(EXCLUDED.downloaded_at, subtitles.downloaded_at),
                            subtitle_format = EXCLUDED.subtitle_format,
                            series_name = EXCLUDED.series_name,
                            episode_title = EXCLUDED.episode_title
                    """, (
                        episode_id, 
                        sub_status, 
                        datetime.now() if has_subtitles else None,
                        subtitle_format,
                        series_info["name"],
                        episode_info["title"]
                    ))
                    
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error adding download to DB: {e}")

    def get_episodes_needing_subtitles(self, series_url: str) -> list[dict]:
        """
        Find episodes for a series that:
        1. Have been downloaded (video exists)
        2. Do NOT have subtitles marked as 'downloaded' in the subtitles table
        """
        try:
            tver_series_id = self._extract_series_id(series_url)
            self.logger.debug(f"Checking missing subtitles for series ID: {tver_series_id}")

            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    # We no longer strictly require 'has_subtitles' to be true in the series table
                    # because we want to retry if it was previously marked false falsely.

                    # Find episodes missing subtitles
                    # matches: series matches, video downloaded, subtitle NOT downloaded (or no entry)
                    query = """
                        SELECT e.episode_url, e.title, e.episode_number
                        FROM episodes e
                        JOIN series s ON e.series_id = s.id
                        JOIN downloads d ON e.id = d.episode_id
                        LEFT JOIN subtitles sub ON e.id = sub.episode_id
                        WHERE s.tver_series_id = %s
                          AND d.status = 'downloaded'
                          AND (sub.status IS NULL OR sub.status != 'downloaded')
                    """
                    cur.execute(query, (tver_series_id,))
                    rows = cur.fetchall()
                    
                    episodes = []
                    for row in rows:
                        episodes.append({
                            "url": row['episode_url'],
                            "title": row['title'],
                            "episode_number": row['episode_number']
                        })
                    
                    if episodes:
                        self.logger.info(f"Found {len(episodes)} episodes needing subtitles in history for {tver_series_id}")
                    return episodes
        except Exception as e:
            self.logger.error(f"Error checking for missing subtitles: {e}")
            return []
