from unittest.mock import MagicMock, patch

from tver_downloader import TVerDownloader


class TestTVerDownloader:
    def setup_method(self):
        self.downloader = TVerDownloader(debug=True)
        self.downloader.config = {
            "download_path": "./downloads",
            "archive_file": "downloaded.txt",
            "yt_dlp_options": [],
        }

    @patch("subprocess.run")
    def test_download_episodes_success(self, mock_run):
        # Mock the subprocess.run to simulate successful download
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Downloading episode 1\n[download] Destination: ./downloads/episode1.mp4\n",
        )

        episodes = [{"url": "http://example.com/episode1", "title": "Episode 1", "id": "1"}]
        result = self.downloader.download_episodes(episodes, "Example Series", {})

        assert result == 1
        assert "episode1.mp4" in self.downloader.download_report["Example Series"]

    @patch("subprocess.run")
    def test_download_episodes_no_episodes(self, mock_run):
        result = self.downloader.download_episodes([], "Example Series", {})
        assert result == 0

    @patch("subprocess.run")
    def test_download_episodes_error(self, mock_run):
        # Mock the subprocess.run to simulate an error
        mock_run.return_value = MagicMock(returncode=1, stderr="Error downloading episode")

        episodes = [{"url": "http://example.com/episode1", "title": "Episode 1", "id": "1"}]
        result = self.downloader.download_episodes(episodes, "Example Series", {})

        assert result == 0
        assert "Error downloading episode" in self.downloader.logger.handlers[0].stream.getvalue()
