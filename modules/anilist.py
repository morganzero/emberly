import requests
from datetime import datetime

def get_current_season():
    month = datetime.now().month
    if month in [12, 1, 2]:
        return "WINTER"
    elif month in [3, 4, 5]:
        return "SPRING"
    elif month in [6, 7, 8]:
        return "SUMMER"
    else:
        return "FALL"

def fetch_anilist_current_season_anime(limit=30):
    season = get_current_season()
    year = datetime.now().year

    gql_query = """
    query ($season: MediaSeason, $seasonYear: Int, $perPage: Int) {
      Page(perPage: $perPage) {
        media(season: $season, seasonYear: $seasonYear, type: ANIME, sort: POPULARITY_DESC) {
          id
          idMal
          title {
            romaji
            english
            native
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

    response = requests.post(
        "https://graphql.anilist.co",
        json={"query": gql_query, "variables": variables},
        headers={"Content-Type": "application/json"}
    )

    response.raise_for_status()
    data = response.json()
    media = data.get("data", {}).get("Page", {}).get("media", [])

    # Returnera i Emberly-vänlig struktur
    result = []
    for item in media:
        result.append({
            "title": item["title"].get("romaji") or item["title"].get("english"),
            "ids": {
                "mal": str(item["idMal"]),
                "anilist": str(item["id"])
            }
        })
    return result
