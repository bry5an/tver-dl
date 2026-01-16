
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
import ssl
import certifi
from typing import Dict, List, Optional
from .utils import traverse_obj

class TVerClient:
    """Client for interactions with TVer's API."""

    _HEADERS = {
        'x-tver-platform-type': 'web',
        'Origin': 'https://tver.jp',
        'Referer': 'https://tver.jp/',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.platform_uid = None
        self.platform_token = None
        # Create SSL context using certifi
        try:
            self.logger.debug(f"Using certifi CA bundle: {certifi.where()}")
            self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        except Exception as e:
            self.logger.warning(f"Failed to create secure SSL context: {e}. Defaulting to unverified.")
            self.ssl_context = ssl._create_unverified_context()
            
        self._initialize_session()

    def _send_request(self, req: urllib.request.Request):
        """Send request with SSL error handling and retry logic."""
        try:
            return urllib.request.urlopen(req, context=self.ssl_context)
        except urllib.error.URLError as e:
            # Check if this is an SSL error
            error_str = str(e.reason)
            if "CERTIFICATE_VERIFY_FAILED" in error_str:
                self.logger.warning("SSL verification failed. Falling back to unverified context.")
                # Switch to unverified context for future requests too
                self.ssl_context = ssl._create_unverified_context()
                # Retry immediately
                return urllib.request.urlopen(req, context=self.ssl_context)
            raise

    def _initialize_session(self):
        """Initialize session to get platform tokens."""
        url = 'https://platform-api.tver.jp/v2/api/platform_users/browser/create'
        data = 'device_type=pc'.encode('utf-8')
        
        try:
            req = urllib.request.Request(url, data=data, headers=self._HEADERS, method='POST')
            with self._send_request(req) as response:
                resp_json = json.loads(response.read().decode())
                
            self.platform_uid = traverse_obj(resp_json, ('result', 'platform_uid'))
            self.platform_token = traverse_obj(resp_json, ('result', 'platform_token'))
            
            if not self.platform_uid or not self.platform_token:
                self.logger.warning("Failed to retrieve TVer platform credentials.")
            else:
                self.logger.debug(f"TVer session initialized. UID: {self.platform_uid}")
                
        except Exception as e:
            self.logger.error(f"Error initializing TVer session: {e}")

    def _call_api(self, url: str, query: Dict = None) -> Dict:
        """Helper to call TVer APIs."""
        try:
            if query is not None:
                # Add platform credentials if available and not already present
                if self.platform_uid and self.platform_token:
                    if 'platform_uid' not in query:
                        query['platform_uid'] = self.platform_uid
                    if 'platform_token' not in query:
                        query['platform_token'] = self.platform_token
                
                url_parts = list(urllib.parse.urlparse(url))
                query_parts = dict(urllib.parse.parse_qsl(url_parts[4]))
                query_parts.update(query)
                url_parts[4] = urllib.parse.urlencode(query_parts)
                url = urllib.parse.urlunparse(url_parts)

            self.logger.debug(f"Calling API: {url}")
            req = urllib.request.Request(url, headers=self._HEADERS)
            
            with self._send_request(req) as response:
                return json.loads(response.read().decode())
                
        except urllib.error.HTTPError as e:
            self.logger.error(f"HTTP Error calling {url}: {e.code} - {e.reason}")
            return {}
        except Exception as e:
            self.logger.error(f"Error calling {url}: {e}")
            return {}

    def get_series_episodes(self, series_id: str, series_name: str) -> List[Dict]:
        """
        Fetch all available episodes for a series ID.
        Returns a list of dicts with keys: id, title, url, episode_number, etc.
        """
        self.logger.info(f"Fetching episodes for series: {series_name}")
        episodes = []

        # 1. Get Seasons
        seasons_url = f'https://service-api.tver.jp/api/v1/callSeriesSeasons/{series_id}'
        
        seasons_data = self._call_api(seasons_url)
        
        contents = traverse_obj(seasons_data, ('result', 'contents'), default=[])
        season_ids = []
        
        for content in contents:
            if content.get('type') == 'season':
                s_id = traverse_obj(content, ('content', 'id'))
                if s_id:
                    season_ids.append(s_id)
        
        if not season_ids:
            self.logger.warning(f"No seasons found for series {series_name}. Trying to check if it's a single season/flat series?")
            return []

        self.logger.debug(f"Found {len(season_ids)} seasons.")

        # 2. Get Episodes for each Season
        for s_id in season_ids:
            episodes_url = f'https://platform-api.tver.jp/service/api/v1/callSeasonEpisodes/{s_id}'
            # This requires platform tokens
            ep_data = self._call_api(episodes_url, query={})
            
            ep_contents = traverse_obj(ep_data, ('result', 'contents'), default=[])
            
            for item in ep_contents:
                if item.get('type') == 'episode':
                    content = item.get('content', {})
                    ep_id = content.get('id')
                    
                    if not ep_id:
                        continue
                        
                    # Extract metadata
                    title = content.get('title', '')
                    series_title = content.get('seriesTitle', '')
                    broadcast_date = content.get('broadcastDateLabel', '')
                    
                    # Construct full title
                    full_title = f"{series_title} {title}".strip()
                    
                    ep_obj = {
                        'id': ep_id,
                        'title': full_title, # Using full title for filtering
                        'episode_title': title, # Raw episode title
                        'series_title': series_title,
                        'url': f'https://tver.jp/episodes/{ep_id}',
                        'episode_number': content.get('no'),
                        'broadcast_date': broadcast_date,
                    }
                    episodes.append(ep_obj)

        self.logger.info(f"found {len(episodes)} episodes via API.")
        return episodes
