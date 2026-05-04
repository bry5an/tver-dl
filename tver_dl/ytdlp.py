import logging
import subprocess
import threading
import re
from pathlib import Path
from typing import Dict, List, Optional, Callable

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

    def download(self, episodes: List[Dict[str, str]], series_name: str, progress_callback: Optional[Callable[[float], None]] = None, category: Optional[str] = None) -> List[Dict]:
        """Download episodes using yt-dlp and return details of successful downloads."""
        if not episodes:
            return []

        try:
            download_path = self.config.get("download_path", "./downloads")
            if category:
                download_path = str(Path(download_path) / category)

            Path(download_path).mkdir(parents=True, exist_ok=True)
            
            # Filter for subtitles only if requested
            episode_urls = self._prepare_download_list(episodes, download_path)
            if not episode_urls:
                self.logger.info("No episodes need downloading (subtitles check passed).")
                return []

            # Create a lookup map for episodes by ID/URL to easily merge metadata later
            ep_map = {ep["url"]: ep for ep in episodes}

            # Build command WITHOUT archive file options, but WITH print options for metadata
            cmd = self._build_download_command(episode_urls, download_path)
            
            self.logger.info(f"Downloading {len(episodes)} episode(s)...")
            if series_name not in self.download_report:
                self.download_report[series_name] = {"success": [], "missing_subtitles": []}

            # We use --print to output specific metadata after download
            # Format: ID|EpisodeNumber|Filepath|Title
            cmd.extend(["--print", "after_move:RESULT:%(id)s|%(episode_number)s|%(filepath)s|%(title)s"])

            # Enable progress output even if we capture stdout
            if "--progress" not in cmd:
                cmd.append("--progress")
            # Force progress to be strictly on stdout or handled via newline
            # yt-dlp defaults to carriage return for progress. We want newlines or we handle CR.
            # Actually, readline() handles \n. yt-dlp progress uses \r.
            # We can use "--newline" to force newlines for progress, making readline() work for progress too.
            cmd.append("--newline")

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
            
            success_results = []
            stdout_lines = []
            completed_count = 0

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    stdout_lines.append(line)
                    stripped_line = line.strip()
                    
                    # Check for progress
                    # [download]  23.5% of 10.00MiB ...
                    progress_match = re.search(r'\[download\]\s+(\d+\.?\d*)%', stripped_line)
                    if progress_match and progress_callback:
                        percent = float(progress_match.group(1))
                        # Total progress = completed episodes + current partial
                        total_progress = completed_count + (percent / 100.0)
                        progress_callback(total_progress)
                    
                    # Check for our custom output
                    if stripped_line.startswith("RESULT:"):
                        try:
                            # Parse result
                            _, data = stripped_line.split("RESULT:", 1)
                            vid_id, ep_num, filepath, title = data.split("|", 3)
                            
                            original_ep = next((e for e in episodes if e.get("id") == vid_id), None)
                            url = original_ep["url"] if original_ep else "unknown"
                            ep_title = original_ep["title"] if original_ep else title

                            success_results.append({
                                "series_name": series_name,
                                "episode_name": ep_title,
                                "url": url,
                                "episode_number": ep_num if ep_num != "NA" else None,
                                "filepath": filepath
                            })
                            
                            # Increment completed count
                            completed_count += 1
                            if progress_callback:
                                progress_callback(float(completed_count))

                        except ValueError:
                            pass # parsing error

            stdout, stderr = process.communicate()
            
            # Additional processing for subtitles if needed (checks existence)
            self._process_download_results(success_results, download_path, series_name)
            
            if process.returncode == 0:
                self.logger.info("✓ Download process completed")
                return success_results
            else:
                self.logger.error(f"✗ Download failed: {stderr}")
                return success_results # Return partial successes

        except Exception as e:
            self.logger.error(f"✗ Download error: {e}", exc_info=self.debug)
            return []

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

    def _build_download_command(self, urls: List[str], download_path: str) -> List[str]:
        """Build the yt-dlp command based on configuration."""
        base_options = list(self.config.get("yt_dlp_options", []))

        if self.subtitles_only:
            # Safely remove -o/--output and its argument
            new_options = []
            skip_next = False
            for i, opt in enumerate(base_options):
                if skip_next:
                    skip_next = False
                    continue
                if opt in ("-o", "--output"):
                    skip_next = True
                    continue
                new_options.append(opt)
            base_options = new_options

            if "--skip-download" not in base_options:
                base_options.insert(0, "--skip-download")
            if "--write-subs" not in base_options:
                base_options.append("--write-subs")
            # Ensure Japanese subs
            if "--sub-lang" in base_options:
                try:
                    idx = base_options.index("--sub-lang")
                    # Remove the flag and its argument
                    base_options.pop(idx)
                    if idx < len(base_options):
                        base_options.pop(idx)
                except ValueError:
                    pass
            base_options.extend(["--sub-lang", "ja"])

            # Explicitly set output template for subtitles to avoid .unknown_video
            # We use the config's output template if we can find it, otherwise default
            # But wait, we just removed it. 
            # If the user has a preferred structure, we should keep it but adapt it?
            # Actually, yt-dlp might fail to name the subtitle correctly without the video.
            # Let's enforce a standard template for subtitles-only to match what we expect
            # or try to extract the user's template.
            # A safe bet is:
            base_options.extend(["--convert-subs", "vtt"])
            base_options.extend(["-o", f"{download_path}/%(series)s/%(title)s"])

        cmd = [
            "yt-dlp",
            # No archive file here!
            *base_options,
            "-P", download_path,
            *urls
        ]
        
        if self.debug:
            cmd.append("-v")
            
        return cmd

    def _process_download_results(self, results: List[Dict], download_path: str, series_name: str):
        """Check for subtitles and update report."""
        download_dir = Path(download_path)
        
        for item in results:
            episode_name = item["episode_name"]
            # Check if subtitle exists for this episode
            subtitle_format = self._get_subtitle_format(download_dir, episode_name)
            
            # Update the result item with subtitle status for history tracking
            item["subtitles"] = bool(subtitle_format)
            item["subtitle_format"] = subtitle_format
            
            self.download_report[series_name]["success"].append(episode_name)
            
            if not subtitle_format:
                self.logger.warning(f"Missing subtitle for: {episode_name}")
                self.download_report[series_name]["missing_subtitles"].append(episode_name)

    def _has_subtitle(self, download_dir: Path, title: str) -> bool:
        """Check if any subtitle file exists for the title."""
        return bool(self._get_subtitle_format(download_dir, title))

    def _get_subtitle_format(self, download_dir: Path, title: str) -> Optional[str]:
        """Return the extension of the subtitle file if it exists."""
        # Sanitize title for globbing if needed, though usually yt-dlp cleans it.
        # We'll try to match the title in the filename.
        # Note: glob might be sensitive to special chars in title.
        for ext in ["vtt", "srt", "ass"]:
            # Escape brackets for glob if they exist in title
            safe_title = title.replace("[", "[[]").replace("]", "[]]")
            if list(download_dir.glob(f"**/*{safe_title}*.{ext}")):
                return ext
        return None
