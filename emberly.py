import yaml
import json
import os
import time
import requests
from pathlib import Path
import logging
from datetime import datetime
from modules.trakt import ensure_trakt_token
from modules.emby import fetch_emby_items


# Setup logging
log_dir = Path("/logs")
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"emberly_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8")
    ]
)

def log(msg, level='info'):
    getattr(logging, level)(msg)


start_time = time.time()

# Load config
with open("configs/config.yaml", "r") as f:
    config = yaml.safe_load(f)

log("🕒 Job started.")

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

# Fetch local media IDs and paths
log("[DEBUG] Fetching Emby items...")
media_cache = {}
for idx, media_type in enumerate(["movies", "series", "anime"], 1):
    log(f"[DEBUG] ({idx}/3) Fetching Emby items for: {media_type}")
    if config['sources'].get(media_type):
        media_cache[media_type] = fetch_emby_items(config, media_type)  # expected dict: {tmdb_id: path}

log("Media cache updated.")

# Fetch trending from Trakt

# Check for Trakt trending cache
trakt_cache_file = Path("configs/.trakt_cache.json")
use_cache = trakt_cache_file.exists() and (time.time() - trakt_cache_file.stat().st_mtime) < 3600

if use_cache:
    log("[CACHE] Using cached Trakt trending data.")
    with open(trakt_cache_file, "r", encoding="utf-8") as f:
        trending = json.load(f)
else:
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
        with open(trakt_cache_file, "w", encoding="utf-8") as f:
            json.dump(trending, f, indent=2)

# Match and resolve paths
matches = {"movies": [], "series": [], "anime": []}

def resolve_and_match(media_type):
    log(f"[DEBUG] Resolving {len(trending[media_type])} trending {media_type}")
    log(f"[DEBUG] Emby cache for {media_type}: {len(media_cache.get(media_type, {}))} items")
    log(f"[DEBUG] Sample Emby IDs: {list(media_cache.get(media_type, {}).keys())[:10]}")

    for item in trending[media_type]:
        # Rätt struktur per typ
        if media_type == "movies":
            ids = item.get("movie", {}).get("ids", {})
        elif media_type == "series":
            ids = item.get("show", {}).get("ids", {})
        else:
            ids = item.get("ids", {})

        # Välj rätt ID
        if media_type == "series":
            external_id = str(ids.get("tvdb") or ids.get("tmdb")) if ids else None
            used_id_type = "tvdb" if "tvdb" in ids else "tmdb" if "tmdb" in ids else None
        else:
            external_id = str(ids.get("tmdb")) if ids else None
            used_id_type = "tmdb"

        if not external_id:
            log(f"[DEBUG] Skipping item, no {used_id_type.upper() if used_id_type else 'usable'} ID found.")
            continue

        log(f"[TRACE] Trying {used_id_type.upper()} ID: {external_id}")
        if media_type == "series" and used_id_type == "tmdb":
            log(f"[DEBUG] Fallback TMDB ID used for series: {external_id}")

        path = media_cache.get(media_type, {}).get(external_id)
        if path:
            log(f"  ✅  Match: {external_id} => {path}")
            matches[media_type].append((external_id, path))

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
        content_dir = src_path
        if not content_dir.is_dir():
            content_dir = content_dir.parent
        link_name = content_dir.name.replace("'", "").replace('"', '')
        link_path = target_path / link_name

        if link_path.exists():
            try:
                if not link_path.samefile(content_dir):
                    link_path.unlink()
                else:
                    continue  # already correct
            except FileNotFoundError:
                link_path.unlink()

        if not link_path.exists():
            link_path.symlink_to(content_dir, target_is_directory=True)
            new_links.add(link_name)
            added.append(link_name)

    for link in existing_links - new_links:
        (target_path / link).unlink()
        removed.append(link)

    return added, removed

# Run symlink creation for all types
added_m, removed_m = create_symlinks(matches["movies"], config['symlink_paths']['trending_movies'], "movies") if config['sources'].get('movies') else ([], [])
added_s, removed_s = create_symlinks(matches["series"], config['symlink_paths']['trending_series'], "series") if config['sources'].get('series') else ([], [])
added_a, removed_a = create_symlinks(matches["anime"], config['symlink_paths'].get('current_season_anime', '/emberly/anime'), "anime") if config['sources'].get('anime') else ([], [])

# Final log
log("Symlinks updated:")
print(f"  ➕   Movies added: {len(added_m)}")
print(f"  ➖   Movies removed: {len(removed_m)}")
print(f"  ➕   Series added: {len(added_s)}")
print(f"  ➖   Series removed: {len(removed_s)}")
print(f"  ➕   Anime added: {len(added_a)}")
print(f"  ➖   Anime removed: {len(removed_a)}")

elapsed = time.time() - start_time
log(f"✅  Job finished in {elapsed:.2f}s. Next run at {config['schedule']['hour']}:{config['schedule']['minute'].zfill(2)}.")
