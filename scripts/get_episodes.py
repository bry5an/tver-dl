import argparse
import json
import sys
import requests

TVER_ORIGIN = "https://tver.jp"

HEADERS_COMMON = {
    "Origin": TVER_ORIGIN,
    "Referer": f"{TVER_ORIGIN}/",
    "x-tver-platform-type": "web",
}

def init_session():
    url = "https://platform-api.tver.jp/v2/api/platform_users/browser/create"
    headers = {
        **HEADERS_COMMON,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    resp = requests.post(url, headers=headers, data={"device_type": "pc"})
    resp.raise_for_status()
    result = resp.json()["result"]

    return result["platform_uid"], result["platform_token"]

def get_seasons(series_id):
    url = f"https://service-api.tver.jp/api/v1/callSeriesSeasons/{series_id}"
    resp = requests.get(url, headers=HEADERS_COMMON)
    resp.raise_for_status()

    contents = resp.json()["result"]["contents"]
    return [
        c["content"]
        for c in contents
        if c.get("type") == "season"
    ]

def get_episodes(season_id, uid, token):
    url = f"https://platform-api.tver.jp/service/api/v1/callSeasonEpisodes/{season_id}"

    headers = {
        **HEADERS_COMMON,
        "x-tver-platform-uid": uid,
        "x-tver-platform-token": token,
    }

    params = {
        "platform_uid": uid,
        "platform_token": token,
    }

    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()["result"]

def main():
    parser = argparse.ArgumentParser(
        description="Fetch TVer seasons and episodes"
    )
    parser.add_argument(
        "series_id",
        help="Series ID (e.g. sr9gfdf2ex)"
    )
    parser.add_argument(
        "--season-id",
        help="Fetch only a specific season ID"
    )
    parser.add_argument(
        "--season-title",
        help="Fetch seasons matching this title (e.g. 本編)"
    )
    parser.add_argument(
        "-o", "--output",
        default="./json_output/tver_episodes.json",
        help="Output JSON file (default: tver_episodes.json)"
    )

    args = parser.parse_args()

    uid, token = init_session()
    seasons = get_seasons(args.series_id)

    # Filter seasons
    if args.season_id:
        seasons = [s for s in seasons if s["id"] == args.season_id]
        if not seasons:
            sys.exit("❌ No season found with that season-id")

    if args.season_title:
        seasons = [s for s in seasons if s["title"] == args.season_title]
        if not seasons:
            sys.exit("❌ No seasons matched that season-title")

    output = {
        "series_id": args.series_id,
        "seasons": [],
    }

    for season in seasons:
        season_data = {
            "season_id": season["id"],
            "title": season["title"],
            "episodes": get_episodes(season["id"], uid, token),
        }
        output["seasons"].append(season_data)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Wrote {len(output['seasons'])} season(s) to {args.output}")

if __name__ == "__main__":
    main()
