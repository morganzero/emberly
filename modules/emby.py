import requests

def fetch_emby_items(config, media_type):
    """
    Fetch TMDB IDs for given media type from all Emby instances.
    Returns a dictionary: { tmdb_id (str): None }
    """
    tmdb_ids = set()

    for instance in config['emby']['instances']:
        headers = {"X-Emby-Token": instance['api_key']}
        url = f"{instance['url']}/emby/Items"
        params = {
            "Recursive": "true",
            "IncludeItemTypes": "Series" if media_type == "series" else "Movie",
            "Fields": "ProviderIds"
        }

        print(f"[DEBUG] Fetching Emby items for type '{media_type}' from {url}")

        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            items = response.json().get("Items", [])

            for item in items:
                provider_ids = item.get("ProviderIds", {})
                tmdb_id = provider_ids.get("Tmdb") or provider_ids.get("tmdb")
                if tmdb_id:
                    tmdb_ids.add(str(tmdb_id))

        except requests.RequestException as e:
            print(f"[ERROR] Failed to fetch Emby items from {instance['url']}: {e}")

    return tmdb_ids

def fetch_path_for_tmdb(config, tmdb_id, media_type):
    """
    Fetch the media path for a specific TMDB ID and type.
    """
    for instance in config['emby']['instances']:
        headers = {"X-Emby-Token": instance['api_key']}
        url = f"{instance['url']}/emby/Items"
        params = {
            "Recursive": "true",
            "IncludeItemTypes": "Series" if media_type == "series" else "Movie",
            "Fields": "ProviderIds,Path"
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            items = response.json().get("Items", [])

            for item in items:
                provider_ids = item.get("ProviderIds", {})
                emby_tmdb = provider_ids.get("Tmdb") or provider_ids.get("tmdb")
                if str(emby_tmdb) == str(tmdb_id):
                    return item.get("Path")

        except requests.RequestException as e:
            print(f"[ERROR] Could not fetch path for TMDB ID {tmdb_id} from {instance['url']}: {e}")

    return None
