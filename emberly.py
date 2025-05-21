import yaml
import json
import os
import time
import requests
from pathlib import Path
from modules.trakt import ensure_trakt_token
from emby import fetch_emby_items, fetch_path_for_tmdb

start_time = time.time()

# Load config
with open("configs/config.yaml", "r") as f:
    config = yaml.safe_load(f)

print("🕒 Job started.")

# Authenticate with Trakt
if not config['sources'].get('trakt'):
    print("❌ Trakt not enabled in config. Exiting.")
    exit(1)

tokens = ensure_trakt_token(config, save_to_config=True)
access_token = tokens.get("access_token")
if not access_token:
    print("❌ No Trakt access token available. Exiting.")
    exit(1)

print(f"[DEBUG] Trakt token begins with: {access_token[:6]}...")

# Fetch local media IDs
print("[DEBUG] Fetching Emby items...")
media_cache = {}
for media_type in ["movies", "series", "anime"]:
    if config['sources'].get(media_type):
        # fetch_emby_items now returns {tmdb_id: path}
        media_cache[media_type] = fetch_emby_items(config, media_type)

print("Media cache updated.")

# Fetch trending from Trakt with pagination
trending = {"movies": [], "series": [], "anime": []}

headers = {
    "Authorization": f"Bearer {access_token}",
    "trakt-api-version": "2",
    "trakt-api-key": config['trakt']['client_id']
}

def fetch_trending_paginated(media_type):
    all_items = []
    limit = config.get("trending_limit", {}).get(media_type, 30)
    page = 1
    while len(all_items) < limit:
        url = f"https://api.trakt.tv/{media_type}/trending?page={page}"
        print(f"[DEBUG] Fetching: {url}")
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            break
        items = r.json()
        if not items:
            break
        all_items.extend(items)
        if len(items) < 38:
            break
        page += 1
    return all_items[:limit]

media_type_map = {"movies": "movies", "series": "shows"}
for local_type, trakt_type in media_type_map.items():
        if config['sources'].get(local_type):
        trending[local_type] = fetch_trending_paginated(trakt_type)

# Match and resolve full paths
matches = {"movies": [], "series": [], "anime": []}

def resolve_and_match(media_type):
    for item in trending[media_type]:
        ids = item.get("ids") or item.get("show", {}).get("ids", {})
        tmdb_id = str(ids.get("tmdb"))
        if not tmdb_id:
            print(f"[DEBUG] Skipping item, no TMDB ID found.")
            continue
        path = media_cache.get(media_type, {}).get(tmdb_id)
        if path:
            if path:
                print(f"  ✅  Match: {tmdb_id} => {path}")
                matches[media_type].append((tmdb_id, path))

for mt in ["movies", "series", "anime"]:
    if config['sources'].get(mt):
        resolve_and_match(mt)

# Create symlinks

def create_symlinks(matches, target_dir, media_type):
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    existing_links = {f.name for f in target_path.iterdir() if f.is_symlink()}
    new_links = set()
    added, removed = [], []

    for _, src in matches:
        src_path = Path(src)
        if not src_path.exists():
            continue
        content_dir = src_path.parent
        link_name = content_dir.name.replace("'", "").replace('"', '')
        link_path = target_path / link_name

        try:
            if link_path.exists() and not link_path.samefile(content_dir):
                            link_path.unlink()
        except FileNotFoundError:
            link_path.unlink()
        elif link_path.exists():
            continue

        link_path.symlink_to(content_dir, target_is_directory=True)
        new_links.add(link_name)
        added.append(link_name)

    for link in existing_links - new_links:
        (target_path / link).unlink()
        removed.append(link)

    return added, removed

added_m, removed_m = create_symlinks(matches["movies"], config['symlink_paths']['trending_movies'], "movies") if config['sources'].get('movies') else ([], [])
added_s, removed_s = create_symlinks(matches["series"], config['symlink_paths']['trending_series'], "series") if config['sources'].get('series') else ([], [])
added_a, removed_a = create_symlinks(matches["anime"], config['symlink_paths'].get('current_season_anime', '/emberly/anime'), "anime") if config['sources'].get('anime') else ([], [])

print("Symlinks updated:")
print(f"  ➕   Movies added: {len(added_m)}")
print(f"  ➖   Movies removed: {len(removed_m)}")
print(f"  ➕   Series added: {len(added_s)}")
print(f"  ➖   Series removed: {len(removed_s)}")
print(f"  ➕   Anime added: {len(added_a)}")
print(f"  ➖   Anime removed: {len(removed_a)}")

elapsed = time.time() - start_time
print(f"✅  Job finished in {elapsed:.2f}s. Next run at {config['schedule']['hour']}:{config['schedule']['minute'].zfill(2)}.")
