import logging
import pytest
from tver_dl.tracker import CSVTracker, DatabaseTracker


@pytest.fixture
def csv_tracker(tmp_path):
    return CSVTracker(tmp_path / "history.csv", logging.getLogger("test"))


SERIES = {"name": "テスト番組", "url": "https://tver.jp/series/abc123"}
EPISODE = {"title": "第1話", "url": "https://tver.jp/episodes/ep001", "episode_number": "1"}
DOWNLOAD = {"filepath": None, "subtitles": False}


class TestCSVTrackerHasEpisode:
    def test_empty_history_returns_false(self, csv_tracker):
        assert not csv_tracker.has_episode("https://tver.jp/episodes/ep001")

    def test_added_episode_found(self, csv_tracker):
        csv_tracker.add_download(SERIES, EPISODE, DOWNLOAD)
        assert csv_tracker.has_episode(EPISODE["url"])

    def test_different_url_not_found(self, csv_tracker):
        csv_tracker.add_download(SERIES, EPISODE, DOWNLOAD)
        assert not csv_tracker.has_episode("https://tver.jp/episodes/ep999")

    def test_multiple_episodes(self, csv_tracker):
        ep2 = {**EPISODE, "url": "https://tver.jp/episodes/ep002", "episode_number": "2"}
        csv_tracker.add_download(SERIES, EPISODE, DOWNLOAD)
        csv_tracker.add_download(SERIES, ep2, DOWNLOAD)
        assert csv_tracker.has_episode(EPISODE["url"])
        assert csv_tracker.has_episode(ep2["url"])
        assert not csv_tracker.has_episode("https://tver.jp/episodes/ep003")


class TestCSVTrackerPersistence:
    def test_history_persists_across_instances(self, tmp_path):
        path = tmp_path / "history.csv"
        t1 = CSVTracker(path, logging.getLogger("test"))
        t1.add_download(SERIES, EPISODE, DOWNLOAD)

        t2 = CSVTracker(path, logging.getLogger("test"))
        assert t2.has_episode(EPISODE["url"])

    def test_creates_missing_parent_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "history.csv"
        tracker = CSVTracker(nested, logging.getLogger("test"))
        assert nested.exists()


class TestDatabaseTrackerExtractSeriesId:
    def test_extracts_id_from_standard_url(self):
        t = DatabaseTracker.__new__(DatabaseTracker)
        assert t._extract_series_id("https://tver.jp/series/abc123") == "abc123"

    def test_extracts_alphanumeric_id(self):
        t = DatabaseTracker.__new__(DatabaseTracker)
        assert t._extract_series_id("https://tver.jp/series/ABC123xyz") == "ABC123xyz"

    def test_fallback_for_unknown_url_format(self):
        t = DatabaseTracker.__new__(DatabaseTracker)
        result = t._extract_series_id("https://example.com/something/myid")
        assert result == "myid"


class TestDatabaseTrackerBatchEmpty:
    def test_empty_url_list_returns_empty_set(self):
        t = DatabaseTracker.__new__(DatabaseTracker)
        t.logger = logging.getLogger("test")
        assert t.has_episodes_batch([]) == set()
