#!/usr/bin/env python3
"""Fill in character details from the Blizzard profile API. Off by default.

Blizzard has not published the WoW: Forever profile namespace yet. Once it
does, the "Character sync (off)" workflow can run this script. It updates
level, race, class and faction for every character in data/characters.json
that has an "armory" block, for example:

    "armory": { "realm": "realm-slug" }

Hand-written fields (name, ruleset, status, featured) are never changed, and
the site never depends on this script.

Environment (set as repository secrets and variables, see README):
  BLIZZARD_CLIENT_ID, BLIZZARD_CLIENT_SECRET   secrets
  BLIZZARD_REGION                              variable, e.g. "us"
  BLIZZARD_PROFILE_NAMESPACE                   variable, e.g. "profile-forever-us"
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "characters.json"


def access_token(client_id: str, secret: str) -> str:
    request = urllib.request.Request(
        "https://oauth.battle.net/token",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": "Basic " + base64.b64encode(f"{client_id}:{secret}".encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)["access_token"]


def profile(region: str, namespace: str, token: str, realm: str, name: str) -> dict:
    path = f"/profile/wow/character/{urllib.parse.quote(realm.lower())}/{urllib.parse.quote(name.lower())}"
    query = urllib.parse.urlencode({"namespace": namespace, "locale": "en_US"})
    request = urllib.request.Request(
        f"https://{region}.api.blizzard.com{path}?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> int:
    client_id = os.environ.get("BLIZZARD_CLIENT_ID", "")
    secret = os.environ.get("BLIZZARD_CLIENT_SECRET", "")
    region = os.environ.get("BLIZZARD_REGION", "") or "us"
    namespace = os.environ.get("BLIZZARD_PROFILE_NAMESPACE", "")
    if not (client_id and secret and namespace):
        print("Character sync is not set up yet (missing secrets or namespace). Nothing changed.")
        return 0

    data = json.loads(PATH.read_text(encoding="utf-8"))
    token = access_token(client_id, secret)
    changed = 0
    for character in data.get("characters", []):
        armory = character.get("armory") or {}
        if not armory.get("realm"):
            continue
        try:
            info = profile(armory.get("region", region), namespace, token, armory["realm"], character["name"])
        except urllib.error.HTTPError as err:
            print(f"{character['name']}: HTTP {err.code}, left as is")
            continue
        updates = {
            "level": info.get("level"),
            "race": (info.get("race") or {}).get("name"),
            "class": (info.get("character_class") or {}).get("name"),
            "faction": (info.get("faction") or {}).get("name"),
        }
        for key, value in updates.items():
            if value and character.get(key) != value:
                character[key] = value
                changed += 1
    if changed:
        PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Character sync: {changed} field(s) updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
