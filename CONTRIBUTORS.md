# Contributors Guide

This document assists contributors and advanced users in understanding how to interact with the TVer API manually. This is useful for inspecting raw API responses to find new metadata fields for better episode filtering.

## Inspecting TVer API Responses

To find alternatives to string-based filtering (include/exclude patterns), you can inspect the JSON response from the episode list endpoints.

### Prerequisites

You need `curl` and a terminal. You can also import these requests into Postman.

### Step 1: Initialize Session (Get Tokens)

First, you need to generate a `platform_uid` and `platform_token`. These are required for most API calls.

**Request:**

```bash
curl -X POST "https://platform-api.tver.jp/v2/api/platform_users/browser/create" \
     -H "Origin: https://tver.jp" \
     -H "Referer: https://tver.jp/" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "device_type=pc"
```

**Response (JSON):**

Look for `result.platform_uid` and `result.platform_token`.

```json
{
  "result": {
    "platform_uid": "your_uid_here",
    "platform_token": "your_token_here",
    ...
  }
}
```

### Step 2: Get Series Seasons

Find your `series_id` from the TVer URL (e.g., `https://tver.jp/series/sr9gfdf2ex` -> `sr9gfdf2ex`).

**Request:**

```bash
# Replace {series_id} with your actual ID
curl "https://service-api.tver.jp/api/v1/callSeriesSeasons/sr9gfdf2ex" \
     -H "x-tver-platform-type: web"
```

**Response:**

This returns a list of contents. Look for items where `type` is `season`. Note the `content.id` (season ID) for the next step.

```json
{
  "result": {
    "contents": [
      {
        "type": "season",
        "content": {
          "id": "s0000411",
          "title": "Season Title",
          ...
        }
      }
    ]
  }
}
```

### Step 3: Get Episodes for a Season

Use the `season_id` from Step 2 and the tokens from Step 1.

**Request:**

```bash
# Replace {season_id}, {uid}, and {token}
curl "https://platform-api.tver.jp/service/api/v1/callSeasonEpisodes/s0000411?platform_uid={uid}&platform_token={token}" \
     -H "x-tver-platform-type: web" \
     -H "x-tver-platform-token: {token}" \
     -H "x-tver-platform-uid: {uid}"
```

*Note: The token/uid are usually passed as query parameters, but headers are sometimes respected or required depending on the specific endpoint version.*

**Response (What to look for):**

This JSON contains the rich metadata for each episode. You might find fields like:
- `broadcastDateLabel`: "3月5日(日)放送"
- `isAllowSearch`: true/false
- `isHighlight`: true/false (Often used for "Digests")
- `no`: Episode number (integer)
- `content.title`: "Episode Title"
- `content.seriesTitle`: "Series Name"

Check if there are boolean flags or specific type identifiers that distinguish "Real Episodes" from "Previews" (予告) or "Digests".

### Potential Filtering Logic

If you find a useful field, you can update `TVerClient.get_series_episodes` in `tver_dl/tver_api.py` to extract it, and then update `filter.py` to use it.
