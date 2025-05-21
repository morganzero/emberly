import time
import json
from pathlib import Path

CACHE_FILE = Path("configs/.anilist_cache.json")
CACHE_EXPIRE_MINUTES = 60  # default if not set in config.yaml

def fetch_anilist_current_season_anime(limit=30, config=None):
    expiration = int(config.get("mal", {}).get("cache_expiration", CACHE_EXPIRE_MINUTES)) * 60

    if CACHE_FILE.exists() and time.time() - CACHE_FILE.stat().st_mtime < expiration:
        try:
            with CACHE_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load AniList cache: {e}")
    # Determine current season and year
    from datetime import datetime
    now = datetime.utcnow()
    month = now.month
    year = now.year

    if month in [12, 1, 2]:
        season = "WINTER"
    elif month in [3, 4, 5]:
        season = "SPRING"
    elif month in [6, 7, 8]:
        season = "SUMMER"
    else:
        season = "FALL"

    query = """
    query ($season: MediaSeason, $seasonYear: Int, $perPage: Int) {
      Page(perPage: $perPage) {
        media(season: $season, seasonYear: $seasonYear, type: ANIME, sort: POPULARITY_DESC) {
          id
          idMal
          title {
            romaji
          }
        }
      }
    }
    """

    variables = {
        "season": season,
        "seasonYear": year,
        "perPage": limit
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.post(ANILIST_API, json={"query": query, "variables": variables}, headers=headers)
        response.raise_for_status()
        data = response.json()
        results = []

        for anime in data["data"]["Page"]["media"]:
            ids = {}
            if anime.get("idMal"):
                ids["mal"] = anime["idMal"]
            if anime.get("id"):
                ids["anilist"] = anime["id"]
            results.append({
                "title": anime["title"]["romaji"],
                "ids": ids
            })

        with CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results

    except Exception as e:
        print(f"[ERROR] Failed to fetch from AniList: {e}")
        return []
