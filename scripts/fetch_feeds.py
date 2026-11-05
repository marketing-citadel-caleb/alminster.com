#!/usr/bin/env python3
"""Refresh data/videos.json (latest YouTube uploads) and data/news.json (headlines).

Runs every 15 minutes in GitHub Actions. Standard library only. When a
source is down, the last good data is kept, so an outage never blanks the site.

Videos come from the channel's public RSS feed. If the repository has a
YOUTUBE_API_KEY secret, the YouTube Data API is used as a backup source.
"""
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
USER_AGENT = "alminster.com feed refresher (+https://alminster.com)"
VIDEO_LIMIT = 12
ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"


def fetch(url: str, attempts: int = 3) -> bytes:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def describe(err: Exception) -> str:
    # Never include the URL: the API backup URL carries the key.
    if isinstance(err, urllib.error.HTTPError):
        return f"HTTP {err.code}"
    if isinstance(err, urllib.error.URLError):
        return f"network error: {err.reason}"
    return type(err).__name__


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clean(value: str | None) -> str:
    value = re.sub(r"<[^>]+>", "", html.unescape(value or ""))
    value = value.replace("\u2014", " - ")  # site copy has no em dashes
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value: str | None) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


# ------------------------------------------------------------------ videos

def videos_from_rss(channel_id: str) -> list[dict]:
    root = ET.fromstring(fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"))
    videos = []
    for entry in root.iter(f"{ATOM}entry"):
        video_id = entry.findtext(f"{YT}videoId")
        if video_id:
            videos.append({
                "id": video_id,
                "title": clean(entry.findtext(f"{ATOM}title")),
                "published": iso(parse_date(entry.findtext(f"{ATOM}published"))),
            })
    return videos


def videos_from_api(channel_id: str, key: str) -> list[dict]:
    query = urllib.parse.urlencode({
        "part": "snippet,contentDetails,status",
        "playlistId": "UU" + channel_id[2:],  # the channel's uploads playlist
        "maxResults": VIDEO_LIMIT,
        "key": key,
    })
    data = json.loads(fetch(f"https://www.googleapis.com/youtube/v3/playlistItems?{query}", attempts=2))
    videos = []
    for item in data.get("items", []):
        if item.get("status", {}).get("privacyStatus") != "public":
            continue
        details = item.get("contentDetails", {})
        if details.get("videoId"):
            videos.append({
                "id": details["videoId"],
                "title": clean(item.get("snippet", {}).get("title")),
                "published": iso(parse_date(details.get("videoPublishedAt"))),
            })
    return videos


def refresh_videos() -> None:
    path = DATA / "videos.json"
    site = read_json(DATA / "site.json", {})
    channel_id = str(site.get("youtubeChannelId", "")).strip()
    if not channel_id.startswith("UC"):
        print("videos: no youtubeChannelId in data/site.json; skipped")
        return
    previous = read_json(path, {}).get("videos") or []

    sources = [("rss", lambda: videos_from_rss(channel_id))]
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if key:
        sources.append(("api", lambda: videos_from_api(channel_id, key)))

    for name, get_videos in sources:
        try:
            videos = get_videos()
        except Exception as err:  # any failure falls through to the next source
            print(f"videos: {name} failed ({describe(err)})")
            continue
        if not videos:
            print(f"videos: {name} returned no videos")
            continue
        videos = sorted(videos, key=lambda v: v["published"] or "", reverse=True)[:VIDEO_LIMIT]
        if videos == previous:
            print(f"videos: {name} ok, no change")
        else:
            write_json(path, {"updated": iso(datetime.now(timezone.utc)), "source": name, "videos": videos})
            print(f"videos: {name} ok, saved {len(videos)}")
        return
    print("videos: no source worked this time; keeping the last saved list")


# -------------------------------------------------------------- headlines

def items_from_feed(feed: dict, cutoff: datetime, hidden: set[str]) -> list[dict]:
    root = ET.fromstring(fetch(feed["url"]))
    feed_title = clean(root.findtext("channel/title") or root.findtext(f"{ATOM}title"))
    must = feed.get("titleMustInclude") or []
    must = [w.lower() for w in ([must] if isinstance(must, str) else must)]
    items = []
    for node in [*root.iter("item"), *root.iter(f"{ATOM}entry")]:
        title = clean(node.findtext("title") or node.findtext(f"{ATOM}title"))
        url = (node.findtext("link") or "").strip()
        if not url and node.find(f"{ATOM}link") is not None:
            url = node.find(f"{ATOM}link").get("href", "").strip()
        published = parse_date(node.findtext("pubDate") or node.findtext(f"{ATOM}published") or node.findtext(f"{ATOM}updated"))
        source_el = node.find("source")
        source = feed.get("source") or (clean(source_el.text) if source_el is not None else "") or feed_title
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].rstrip()  # Google News appends " - Publisher"
        if not title or not url.startswith(("https://", "http://")) or source.lower() in hidden:
            continue
        if must and not any(word in title.lower() for word in must):
            continue
        if published and published < cutoff:
            continue
        items.append({"title": title, "url": url, "source": source, "published": iso(published)})
    return items


def last_published_news() -> dict:
    """Headlines from the last good run: the local file, else the copy on the live site.

    news.json is not committed, so on GitHub's servers the live site is the
    only record of what was showing before this run.
    """
    local = read_json(DATA / "news.json", None)
    if local:
        return local
    site_url = str(read_json(DATA / "site.json", {}).get("url", "")).rstrip("/")
    if not site_url.startswith("https://"):
        return {}
    try:
        return json.loads(fetch(f"{site_url}/news.json", attempts=1))
    except Exception:  # first run, or the site is unreachable: start fresh
        return {}


def refresh_news() -> None:
    config = read_json(DATA / "feeds.json", {})
    per_section = int(config.get("itemsPerSection", 5))
    now = iso(datetime.now(timezone.utc))
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(config.get("maxAgeDays", 10)))
    hidden = {str(name).lower() for name in config.get("hideSources", [])}
    last = last_published_news()
    previous = {s.get("title"): s for s in last.get("sections", [])}

    sections = []
    for section in config.get("sections", []):
        title = str(section.get("title", "")).strip()
        feeds = section.get("feeds", [])
        groups, failed = [], False
        for feed in feeds:
            try:
                groups.append(items_from_feed(feed, cutoff, hidden))
            except Exception as err:  # one bad feed never stops the rest
                failed = True
                print(f"news: {title}: {feed.get('url', '?')[:60]} failed ({describe(err)})")
        items = [item for group in groups for item in group]
        updated = now
        if not items and failed and title in previous:
            # Outage: keep what we had, along with when it was fetched, so the site stays honest.
            items = previous[title].get("items", [])
            updated = previous[title].get("updated") or last.get("updated")
        elif section.get("mixSources"):
            # Feeds take turns (newest first within each), so no single outlet fills the column.
            rounds = zip_longest(*(sorted(g, key=lambda i: i["published"] or "", reverse=True) for g in groups))
            items = [item for row in rounds for item in row if item]
        elif len(feeds) > 1:
            # Merge several feeds newest first; a single feed keeps its own (editorial) order.
            items.sort(key=lambda i: i["published"] or "", reverse=True)
        seen, unique = set(), []
        for item in items:
            key = re.sub(r"\W+", "", item["title"].lower())
            if key not in seen:
                seen.add(key)
                unique.append(item)
        sections.append({"title": title, "note": section.get("note", ""), "updated": updated, "items": unique[:per_section]})
        kept = "" if updated == now else " (kept from the last good run)"
        print(f"news: {title}: {len(unique[:per_section])} headlines{kept}")
    write_json(DATA / "news.json", {"updated": now, "sections": sections})


if __name__ == "__main__":
    refresh_videos()
    refresh_news()
