import logging
import subprocess
import threading
from pathlib import Path
from typing import Dict, List

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

    def download(self, episodes: List[Dict[str, str]], series_name: str, progress_callback=None) -> int:
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

            # We can't easily get per-file progress from a single yt-dlp batch command without parsing stdout in real-time.
            # For now, we will run the command and update progress based on the number of files.
            # Ideally, we would run yt-dlp per file or parse stdout line-by-line.
            # Let's parse stdout line-by-line to update progress.
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
            
            stdout_lines = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    stdout_lines.append(line)
                    # Detect download completion of a file
                    if "[download] Destination:" in line or "has already been downloaded" in line:
                        if progress_callback:
                            progress_callback(advance=1)
            
            stdout, stderr = process.communicate() # Get remaining output
            # Combine captured lines with any remaining
            full_stdout = "".join(stdout_lines) + (stdout or "")

            if process.returncode == 0:
                self._process_download_results(full_stdout, download_path, series_name, episodes)
                self.logger.info("✓ Download process completed")
                return len(episodes)
            else:
                self.logger.error(f"✗ Download failed: {stderr}")
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
