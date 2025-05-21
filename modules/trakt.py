import requests
import json
import time
from pathlib import Path
import yaml

def ensure_trakt_token(config, save_to_config=False):
    if 'trakt_token' in config:
        token_data = config['trakt_token']
        if all(k in token_data for k in ['access_token', 'created_at', 'expires_in']):
            now = int(time.time())
            if token_data['created_at'] + token_data['expires_in'] > now:
                return token_data

    if save_to_config and 'trakt_token' in config:
        return config['trakt_token']

    client_id = config['trakt']['client_id']
    client_secret = config['trakt']['client_secret']

    device_code_url = "https://api.trakt.tv/oauth/device/code"
    headers = {"Content-Type": "application/json"}
    response = requests.post(device_code_url, json={"client_id": client_id}, headers=headers)
    data = response.json()

    print(f"\nGo to {data['verification_url']} and enter the code: {data['user_code']}")
    print("Waiting for authorization...")

    token_url = "https://api.trakt.tv/oauth/device/token"
    for _ in range(600):
        time.sleep(data['interval'])
        r = requests.post(token_url, json={
            "code": data['device_code'],
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "public"
        }, headers=headers)

        if r.status_code == 200:
            tokens = r.json()
            if save_to_config:
                config['trakt_token'] = tokens
                with open("config.yaml", "w") as f:
                    yaml.safe_dump(config, f)
            print("Trakt authentication successful.")
            return tokens
        elif r.status_code == 400:
            continue
        else:
            print(f"Error: {r.status_code}")
            break

    raise Exception("Failed to authenticate with Trakt")
