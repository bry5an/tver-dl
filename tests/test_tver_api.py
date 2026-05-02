import json
import logging
from io import BytesIO
from unittest.mock import MagicMock, patch
import pytest
from tver_dl.tver_api import TVerClient


def make_response(data: dict):
    """Return a mock HTTP response that yields JSON."""
    body = json.dumps(data).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


SESSION_RESP = {"result": {"platform_uid": "uid123", "platform_token": "tok456"}}


@pytest.fixture
def client():
    with patch.object(TVerClient, "_initialize_session"):
        c = TVerClient(logging.getLogger("test"))
    c.platform_uid = "uid123"
    c.platform_token = "tok456"
    return c


class TestCallApi:
    def test_returns_parsed_json(self, client):
        payload = {"result": {"foo": "bar"}}
        with patch.object(client, "_send_request", return_value=make_response(payload)):
            result = client._call_api("https://example.com/api")
        assert result == payload

    def test_appends_platform_credentials_to_query(self, client):
        with patch.object(client, "_send_request", return_value=make_response({})) as mock_send:
            client._call_api("https://example.com/api", query={})
        req = mock_send.call_args[0][0]
        assert "platform_uid=uid123" in req.full_url
        assert "platform_token=tok456" in req.full_url

    def test_does_not_overwrite_existing_query_params(self, client):
        with patch.object(client, "_send_request", return_value=make_response({})) as mock_send:
            client._call_api("https://example.com/api", query={"platform_uid": "custom"})
        req = mock_send.call_args[0][0]
        assert "platform_uid=custom" in req.full_url

    def test_http_error_returns_empty_dict(self, client):
        import urllib.error
        with patch.object(client, "_send_request", side_effect=urllib.error.HTTPError(
            url="https://example.com", code=404, msg="Not Found", hdrs={}, fp=None
        )):
            result = client._call_api("https://example.com/api")
        assert result == {}

    def test_generic_error_returns_empty_dict(self, client):
        with patch.object(client, "_send_request", side_effect=Exception("timeout")):
            result = client._call_api("https://example.com/api")
        assert result == {}


class TestGetSeriesEpisodes:
    SEASONS_RESP = {
        "result": {
            "contents": [
                {"type": "season", "content": {"id": "s001", "title": "本編"}},
            ]
        }
    }
    EPISODES_RESP = {
        "result": {
            "contents": [
                {
                    "type": "episode",
                    "content": {
                        "id": "ep001",
                        "title": "第1話",
                        "seriesTitle": "テスト番組",
                        "broadcastDateLabel": "2024-01-01",
                        "no": 1,
                    },
                }
            ]
        }
    }

    def test_returns_episodes_with_expected_fields(self, client):
        responses = [make_response(self.SEASONS_RESP), make_response(self.EPISODES_RESP)]
        with patch.object(client, "_send_request", side_effect=responses):
            episodes = client.get_series_episodes("abc123", "テスト番組")

        assert len(episodes) == 1
        ep = episodes[0]
        assert ep["id"] == "ep001"
        assert ep["title"] == "テスト番組 第1話"
        assert ep["season_name"] == "本編"
        assert ep["url"] == "https://tver.jp/episodes/ep001"
        assert ep["episode_number"] == 1

    def test_no_seasons_returns_empty_list(self, client):
        empty = {"result": {"contents": []}}
        with patch.object(client, "_send_request", return_value=make_response(empty)):
            result = client.get_series_episodes("abc123", "テスト番組")
        assert result == []

    def test_skips_items_without_episode_id(self, client):
        episodes_resp = {
            "result": {
                "contents": [{"type": "episode", "content": {}}]  # no id
            }
        }
        responses = [make_response(self.SEASONS_RESP), make_response(episodes_resp)]
        with patch.object(client, "_send_request", side_effect=responses):
            result = client.get_series_episodes("abc123", "テスト番組")
        assert result == []
