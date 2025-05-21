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
import argparse

# --- Logging setup ---
log_dir = Path("/logs")
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"emberly_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")]
)

def log(msg, level='info'):
    getattr(logging, level)(msg)

# --- CLI flags ---
parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true", help="Simulate run without writing symlinks.")
parser.add_argument("--force", action="store_true", help="Ignore cache and fetch everything fresh.")
args = parser.parse_args()

# --- Load config ---
with open("configs/config.yaml", "r") as f:
    config = yaml.safe_load(f)

start_time = time.time()
log("🕒 Job started.")

# --- Caching ---
cache_exp = config.get("cache_expiration", {})
emby_cache_file = Path("configs/.emby_cache.json")
emby_cache_ttl = cache_exp.get("emby", 3600)

match_cache_file = Path("configs/.match_cache.json")
match_cache_ttl = cache_exp.get("match", 3600)

trakt_cache_file = Path("configs/.trakt_cache.json")
trakt_cache_ttl = cache_exp.get("trakt", 3600)

# --- Trakt auth ---
if not config['sources'].get('trakt'):
    log("❌ Trakt not enabled in config. Exiting.", level="error")
    exit(1)

tokens = ensure_trakt_token(config, save_to_config=True)
access_token = tokens.get("access_token")
if not access_token:
    log("❌ No Trakt access token available. Exiting.", level="error")
    exit(1)

log(f"[DEBUG] Trakt token begins with: {access_token[:6]}...")

# --- Emby fetch with caching ---
def load_emby_cache():
    if emby_cache_file.exists() and (time.time() - emby_cache_file.stat().st_mtime < emby_cache_ttl) and not args.force:
        with emby_cache_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_emby_cache(data):
    with emby_cache_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

media_cache = load_emby_cache()
if not media_cache:
    media_cache = {}
    for idx, media_type in enumerate(["movies", "series", "anime"], 1):
        log(f"[DEBUG] ({idx}/3) Fetching Emby items for: {media_type}")
        if config['sources'].get(media_type):
            media_cache[media_type] = fetch_emby_items(config, media_type) or {}
    save_emby_cache(media_cache)

log("[INFO] Media cache updated.")

# --- Trakt trending fetch ---
trending = {"movies": [], "series": [], "anime": []}
media_type_map = {"movies": "movies", "series": "shows"}

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
        log(f"[DEBUG] Fetching: {url}")
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

use_trakt_cache = trakt_cache_file.exists() and (time.time() - trakt_cache_file.stat().st_mtime < trakt_cache_ttl) and not args.force
if use_trakt_cache:
    with trakt_cache_file.open("r", encoding="utf-8") as f:
        trending.update(json.load(f))
    log("[CACHE] Using cached Trakt trending data.")
else:
    for local_type, trakt_type in media_type_map.items():
        if config['sources'].get(local_type):
            trending[local_type] = fetch_trending_paginated(trakt_type)
    with trakt_cache_file.open("w", encoding="utf-8") as f:
        json.dump(trending, f, indent=2)

# --- Anime trending via AniList ---
if config['sources'].get("anime"):
    from modules.anilist import fetch_anilist_current_season_anime
    limit = config["trending_limit"].get("anime", 30)
    trending["anime"] = fetch_anilist_current_season_anime(limit=limit, config=config)

# --- Match and resolve ---
matches = {"movies": [], "series": [], "anime": []}
summary = {"movies_added": 0, "series_added": 0, "anime_added": 0}

use_match_cache = match_cache_file.exists() and (time.time() - match_cache_file.stat().st_mtime < match_cache_ttl) and not args.force
if use_match_cache:
    with match_cache_file.open("r", encoding="utf-8") as f:
        matches = json.load(f)
else:
    def resolve_and_match(media_type):
        log(f"[DEBUG] Resolving {len(trending[media_type])} trending {media_type}")
        for item in trending[media_type]:
            ids = {}
            if media_type == "movies":
                ids = item.get("movie", {}).get("ids", {})
                keys = ["tmdb", "imdb"]
            elif media_type == "series":
                ids = item.get("show", {}).get("ids", {})
                keys = ["tvdb", "tmdb", "imdb"]
            elif media_type == "anime":
                ids = item.get("ids", {})
                keys = ["mal", "anilist"]

            for k in keys:
                eid = str(ids.get(k)) if k in ids else None
                if eid:
                    path = media_cache.get(media_type, {}).get(eid)
                    if path:
                        log(f"  ✅  Match: {eid} => {path}")
                        matches[media_type].append((eid, path))
                        summary[f"{media_type}_added"] += 1
                        break
            else:
                log(f"[DEBUG] Skipping item, no matching ID found.")

    for mt in ["movies", "series", "anime"]:
        if config['sources'].get(mt):
            resolve_and_match(mt)
    with match_cache_file.open("w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2)

# --- Symlink creation ---
def create_symlinks(matches, target_dir):
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    existing_links = {f.name for f in target_path.iterdir() if f.is_symlink()}
    new_links = set()
    added, removed = [], []

    for _, src in matches:
        src_path = Path(src)
        if not src_path.exists():
            continue
        content_dir = src_path if src_path.is_dir() else src_path.parent
        link_name = content_dir.name.replace("'", "").replace('"', '')
        link_path = target_path / link_name

        if link_path.exists():
            try:
                if not link_path.samefile(content_dir):
                    link_path.unlink()
                else:
                    continue
            except FileNotFoundError:
                link_path.unlink()

        if not link_path.exists():
            if not args.dry_run:
                link_path.symlink_to(content_dir, target_is_directory=True)
            new_links.add(link_name)
            added.append(link_name)

    for link in existing_links - new_links:
        (target_path / link).unlink()
        removed.append(link)

    return added, removed

# --- Apply symlinks ---
added_m, removed_m = create_symlinks(matches["movies"], config['symlink_paths']['trending_movies']) if config['sources'].get('movies') else ([], [])
added_s, removed_s = create_symlinks(matches["series"], config['symlink_paths']['trending_series']) if config['sources'].get('series') else ([], [])
added_a, removed_a = create_symlinks(matches["anime"], config['symlink_paths'].get('current_season_anime', '/emberly/anime')) if config['sources'].get('anime') else ([], [])

# --- Final output ---
log("Symlinks updated:")
print(f"  \u2795   Movies added: {len(added_m)}")
print(f"  \u2796   Movies removed: {len(removed_m)}")
print(f"  \u2795   Series added: {len(added_s)}")
print(f"  \u2796   Series removed: {len(removed_s)}")
print(f"  \u2795   Anime added: {len(added_a)}")
print(f"  \u2796   Anime removed: {len(removed_a)}")

summary["time"] = datetime.now().strftime("%Y-%m-%dT%H:%M")
summary_path = Path("/logs/last_run_summary.json")
with summary_path.open("w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

elapsed = time.time() - start_time
log(f"✅  Job finished in {elapsed:.2f}s. Next run at {config['schedule']['hour']}:{config['schedule']['minute'].zfill(2)}.")