import logging
from unittest.mock import MagicMock, patch, call
import pytest
from tver_dl.tracker import DatabaseTracker


@pytest.fixture
def tracker():
    t = DatabaseTracker.__new__(DatabaseTracker)
    t.logger = logging.getLogger("test")
    t.connection_string = "postgresql://fake"
    t.hostname = "testhost"
    return t


def make_conn(rows=None):
    """Build a mock psycopg2 connection whose cursor returns `rows`."""
    cur = MagicMock()
    cur.fetchall.return_value = rows or []
    cur.fetchone.return_value = [1]
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.__enter__ = lambda s: s
    conn.__exit__ = MagicMock(return_value=False)
    return conn, cur


class TestHasEpisodesBatch:
    def test_returns_matching_urls(self, tracker):
        url = "https://tver.jp/episodes/ep001"
        conn, cur = make_conn(rows=[(url,)])
        with patch.object(tracker, "_get_connection", return_value=conn):
            result = tracker.has_episodes_batch([url, "https://tver.jp/episodes/ep002"])
        assert result == {url}

    def test_none_downloaded_returns_empty_set(self, tracker):
        conn, cur = make_conn(rows=[])
        with patch.object(tracker, "_get_connection", return_value=conn):
            result = tracker.has_episodes_batch(["https://tver.jp/episodes/ep001"])
        assert result == set()

    def test_all_urls_passed_to_query(self, tracker):
        urls = ["https://tver.jp/episodes/ep001", "https://tver.jp/episodes/ep002"]
        conn, cur = make_conn(rows=[])
        with patch.object(tracker, "_get_connection", return_value=conn):
            tracker.has_episodes_batch(urls)
        cur.execute.assert_called_once()
        passed_urls = cur.execute.call_args[0][1][0]
        assert set(passed_urls) == set(urls)

    def test_db_error_returns_empty_set(self, tracker):
        with patch.object(tracker, "_get_connection", side_effect=Exception("connection refused")):
            result = tracker.has_episodes_batch(["https://tver.jp/episodes/ep001"])
        assert result == set()

    def test_has_episode_delegates_to_batch(self, tracker):
        url = "https://tver.jp/episodes/ep001"
        conn, _ = make_conn(rows=[(url,)])
        with patch.object(tracker, "_get_connection", return_value=conn):
            assert tracker.has_episode(url) is True

    def test_has_episode_returns_false_when_missing(self, tracker):
        conn, _ = make_conn(rows=[])
        with patch.object(tracker, "_get_connection", return_value=conn):
            assert tracker.has_episode("https://tver.jp/episodes/ep999") is False
