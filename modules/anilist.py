import requests

def fetch_anilist_trending(media_type, limit=30):
    if media_type not in ["movie", "tv"]:
        return []

    gql_query = """
    query ($type: MediaType, $perPage: Int) {
      Page(perPage: $perPage) {
        media(type: $type, sort: TRENDING_DESC) {
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
        "type": "ANIME",
        "perPage": limit
    }
    response = requests.post(
        "https://graphql.anilist.co",
        json={"query": gql_query, "variables": variables},
        headers={"Content-Type": "application/json"}
    )
    response.raise_for_status()
    data = response.json()
    return data.get("data", {}).get("Page", {}).get("media", [])

def fetch_anidb_trending():
    # Placeholder implementation — AniDB doesn't offer a public trending API
    # This should eventually be replaced with a proper scraper or API client.
    print("[WARN] AniDB trending not yet implemented. Returning empty list.")
    return []
