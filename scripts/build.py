#!/usr/bin/env python3
"""Build alminster.com from the files in data/ and images/ into _site/.

Standard library only. Anything without data is left out of the page
entirely, so visitors never see empty sections, dead buttons or
placeholder text. If a data file has a mistake, the build stops with a
plain message and the live site keeps its last good version.

Run locally:  python scripts/build.py
"""
from __future__ import annotations

import base64
import html
import json
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SRC = ROOT / "src"
IMAGES = ROOT / "images"
OUT = ROOT / "_site"
IMAGE_EXTS = (".webp", ".avif", ".png", ".jpg", ".jpeg", ".svg", ".gif")


class BuildError(Exception):
    pass


# ---------------------------------------------------------------- helpers

def esc(value) -> str:
    return html.escape(str(value), quote=True)


def load(name: str, required: bool = True) -> dict:
    path = DATA / name
    if not path.exists():
        if required:
            raise BuildError(f"data/{name} is missing.")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise BuildError(
            f"data/{name}, line {err.lineno}, column {err.colno}: {err.msg}. "
            "Look for a missing comma, quote or bracket near there."
        ) from None


def text(value) -> str:
    return str(value).strip() if value is not None else ""


def link(value, field: str) -> str:
    """Return a cleaned https link, or "" when the field is left empty."""
    value = text(value)
    if value and not re.fullmatch(r"https://[^\s/]+\.[^\s]+", value):
        raise BuildError(f'"{field}" must be a full link starting with https:// (it is "{value}").')
    return value


def find_image(stem: str) -> str | None:
    """Find images/<stem>.<any image type>, so adding a photo needs no code edit."""
    folder = IMAGES / Path(stem).parent
    base = Path(stem).name.lower()
    if not folder.is_dir():
        return None
    for ext in IMAGE_EXTS:
        for file in sorted(folder.iterdir()):
            if file.is_file() and file.name.lower() == base + ext:
                return file.relative_to(ROOT).as_posix()
    return None


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def nice_date(value: str) -> str:
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (AttributeError, ValueError):
        return text(value)
    return f"{d:%b} {d.day}, {d.year}"


def long_date(value: str) -> str:
    try:
        d = date.fromisoformat(text(value))
    except ValueError:
        return text(value)
    return f"{d:%B} {d.day}, {d.year}"


def ext(url: str, label: str, cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    return f'<a{attr} href="{esc(url)}" target="_blank" rel="noopener">{label}</a>'


def crest(letter: str | None = None) -> str:
    """Original shield emblem. With a letter it becomes a character crest."""
    if letter:
        mark = f'<text x="32" y="40.5" text-anchor="middle" class="crest-letter">{esc(letter)}</text>'
    else:
        mark = '<path class="crest-mark" d="M22.5 44 32 18.5 41.5 44M26.5 35.5h11"/>'
    return (
        '<svg class="crest" viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
        '<path class="crest-shield" d="M32 3 57 11v19c0 15-11 25-25 31C18 55 7 45 7 30V11z"/>'
        '<path class="crest-rim" d="M32 9.5 51 15.5V30c0 11.5-8 19.5-19 24.5C21 49.5 13 41.5 13 30V15.5z"/>'
        f"{mark}</svg>"
    )


PLAY_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M8 5.5v13l10.5-6.5z"/></svg>'
SUN_MOON = (
    '<svg class="icon-sun" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="4.5"/>'
    '<path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3M4.6 4.6l2.1 2.1M17.3 17.3l2.1 2.1M4.6 19.4l2.1-2.1M17.3 6.7l2.1-2.1"/></svg>'
    '<svg class="icon-moon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/></svg>'
)


# ------------------------------------------------------------------ data

def read_site() -> dict:
    site = load("site.json")
    s: dict = {}
    s["name"] = text(site.get("name")) or "Alminster of Azeroth"
    s["url"] = link(site.get("url"), "url").rstrip("/") or "https://alminster.com"
    s["tagline"] = text(site.get("tagline"))
    s["schedule"] = text(site.get("schedule"))
    s["youtube"] = link(site.get("youtube"), "youtube").rstrip("/")
    s["channel_id"] = text(site.get("youtubeChannelId"))
    if not s["youtube"] or not re.fullmatch(r"UC[\w-]{22}", s["channel_id"]):
        raise BuildError('"youtube" and "youtubeChannelId" in data/site.json are required.')
    s["twitch"] = link(site.get("twitch"), "twitch")
    s["kofi"] = link(site.get("kofi"), "kofi")
    s["patreon"] = link(site.get("patreon"), "patreon")
    s["support_line"] = text(site.get("supportLine"))
    email = text(site.get("email"))
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise BuildError(f'"email" in data/site.json does not look like an email address ("{email}").')
    # Reversed and base64-encoded so the address never appears in the HTML.
    s["email_code"] = base64.b64encode(email[::-1].encode()).decode() if email else ""
    s["about"] = [text(p) for p in site.get("about") or [] if text(p)]
    s["about_note"] = text(site.get("aboutNote"))
    s["games"] = site.get("games") or {}

    twitch_channel = ""
    if s["twitch"]:
        match = re.match(r"https://(?:www\.)?twitch\.tv/([A-Za-z0-9_]+)", s["twitch"])
        if not match:
            raise BuildError('"twitch" should look like https://www.twitch.tv/channelname')
        twitch_channel = match.group(1)
    s["twitch_channel"] = twitch_channel

    roster = load("characters.json", required=False)
    s["characters"] = [checked_entry(c, "characters") for c in roster.get("characters") or []]
    s["graveyard"] = [checked_entry(c, "graveyard") for c in roster.get("graveyard") or []]

    s["videos"] = [v for v in load("videos.json", required=False).get("videos") or [] if v.get("id")]
    s["news"] = [sec for sec in load("news.json", required=False).get("sections") or [] if sec.get("items")]

    s["logo"] = find_image("logo")
    s["portrait"] = find_image("portrait")
    s["stream_image"] = find_image("stream")
    s["social_image"] = find_image("social")
    s["has_roster"] = bool(s["characters"] or s["graveyard"])
    s["support"] = [(label, url) for label, url in (("Ko-fi", s["kofi"]), ("Patreon", s["patreon"])) if url]
    return s


def checked_entry(entry, group: str) -> dict:
    if not isinstance(entry, dict) or not text(entry.get("name")):
        raise BuildError(f'Every entry in "{group}" in data/characters.json needs a "name".')
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in entry.items()}


# --------------------------------------------------------------- layout

def page(s: dict, *, title: str, description: str, path: str, prefix: str, current: str, body: str) -> str:
    css = (SRC / "site.css").read_text(encoding="utf-8").replace("{{ROOT}}", prefix)
    canonical = s["url"] + path
    og_image = ""
    if s["social_image"]:
        og_image = f'<meta property="og:image" content="{esc(s["url"] + "/" + s["social_image"])}">'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(s["name"])}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
{og_image}
<meta name="theme-color" content="#14100b" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#f3e9d6" media="(prefers-color-scheme: light)">
<link rel="icon" href="{prefix}assets/emblem.svg" type="image/svg+xml">
<link rel="preload" href="{prefix}assets/fonts/cinzel.woff2" as="font" type="font/woff2" crossorigin>
<script>try{{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}}catch(e){{}}</script>
<style>{css}</style>
<script src="{prefix}assets/site.js" defer></script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{header(s, prefix, current)}
<main id="main">
{body}
</main>
{footer(s)}
</body>
</html>
"""


def header(s: dict, prefix: str, current: str) -> str:
    home = prefix or "./"
    items = [("Videos", f"{prefix}#videos", "")]
    if s["news"]:
        items.append(("News", f"{prefix}#news", ""))
    if s["has_roster"]:
        items.append(("Characters", f"{prefix}characters/", "characters"))
    items.append(("Games", f"{prefix}games/", "games"))
    if s["support"]:
        items.append(("Support", f"{prefix}#support", ""))
    links = []
    for label, href, key in items:
        here = ' aria-current="page"' if key and key == current else ""
        links.append(f'<li><a href="{esc(href)}"{here}>{label}</a></li>')
    if s["logo"]:
        brand = f'<img src="{prefix}{esc(s["logo"])}" alt="{esc(s["name"])}" class="brand-logo">'
    else:
        brand = f'{crest()}<span>Alminster</span>'
    return f"""<header class="topbar">
<div class="wrap topbar-inner">
<a class="brand" href="{esc(home)}" aria-label="{esc(s["name"])} home">{brand}</a>
<a class="btn btn-live btn-sm" href="{esc(s["youtube"])}/live" target="_blank" rel="noopener"><span class="dot" aria-hidden="true"></span>Watch Live</a>
<button class="theme-toggle" type="button" hidden>{SUN_MOON}</button>
<nav class="nav" aria-label="Main"><ul>{"".join(links)}</ul></nav>
</div>
</header>"""


def footer(s: dict) -> str:
    platforms = [ext(s["youtube"], "YouTube")]
    if s["twitch"]:
        platforms.append(ext(s["twitch"], "Twitch"))
    platforms += [ext(url, label) for label, url in s["support"]]
    if s["email_code"]:
        platforms.append(f'<a data-e="{s["email_code"]}" data-needs-js hidden>Email</a>')
    year = datetime.now(timezone.utc).year
    return f"""<footer class="footer">
<div class="wrap">
<ul class="platforms">{"".join(f"<li>{p}</li>" for p in platforms)}</ul>
<p class="fine">Not financial advice. Talk about stocks and markets on stream is commentary only.</p>
<p class="fine">World of Warcraft is a trademark of Blizzard Entertainment, Inc. This is an independent fan site, not affiliated with or endorsed by Blizzard Entertainment.</p>
<p class="fine">&copy; {year} {esc(s["name"])}</p>
</div>
</footer>"""


# ----------------------------------------------------------------- home

def hero(s: dict) -> str:
    if s["logo"]:
        mark = f'<img src="{esc(s["logo"])}" alt="{esc(s["name"])}" class="wordmark-logo" fetchpriority="high">'
    else:
        main, _, sub = s["name"].partition(" of ")
        mark = f'<span class="wm-main">{esc(main)}</span>' + (f'<span class="wm-sub">of {esc(sub)}</span>' if sub else "")
    if s["support"]:
        second = '<a class="btn btn-gold" href="#support">Support the Stream</a>'
    else:
        sub_url = f'https://www.youtube.com/channel/{s["channel_id"]}?sub_confirmation=1'
        second = ext(sub_url, "Subscribe on YouTube", "btn btn-ghost")
    tagline = f'<p class="tagline">{esc(s["tagline"])}</p>' if s["tagline"] else ""
    schedule = ""
    if s["schedule"]:
        schedule = (
            '<p class="schedule"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
            f'{esc(s["schedule"])}</p>'
        )
    poster = ""
    if s["stream_image"]:
        poster = f'<img src="{esc(s["stream_image"])}" alt="" loading="lazy" decoding="async">'
    live_url = s["youtube"] + "/live"
    embed = f'https://www.youtube.com/embed/live_stream?channel={s["channel_id"]}&autoplay=1'
    alt_links = [ext(live_url, "Open on YouTube")]
    if s["twitch"]:
        alt_links.append(
            f'<a href="{esc(s["twitch"])}" target="_blank" rel="noopener" data-twitch="{esc(s["twitch_channel"])}">Watch on Twitch</a>'
        )
    return f"""<section class="hero" id="live" aria-labelledby="hero-title">
<div class="wrap hero-grid">
<div class="hero-copy">
<h1 id="hero-title" class="wordmark">{mark}</h1>
{tagline}
{schedule}
<div class="cta">
<a class="btn btn-live" href="{esc(live_url)}" target="_blank" rel="noopener"><span class="dot" aria-hidden="true"></span>Watch Live</a>
{second}
</div>
</div>
<div class="player-wrap">
<div class="player" id="player">
<a class="facade" href="{esc(live_url)}" target="_blank" rel="noopener" data-embed="{esc(embed)}" data-title="{esc(s["name"])} live stream">
{poster}<span class="play" aria-hidden="true">{PLAY_ICON}</span><span class="facade-label">Play the stream here</span>
</a>
</div>
<p class="player-alt">{" ".join(alt_links)}</p>
</div>
</div>
</section>"""


def support_section(s: dict) -> str:
    if not s["support"]:
        return ""
    buttons = "".join(ext(url, f"Support on {label}", "btn btn-gold") for label, url in s["support"])
    line = f'<p>{esc(s["support_line"])}</p>' if s["support_line"] else ""
    return f"""<section class="section" id="support" aria-labelledby="support-title">
<div class="wrap narrow center panel">
<h2 id="support-title">Support the Stream</h2>
{line}
<div class="cta cta-center">{buttons}</div>
</div>
</section>"""


def about_section(s: dict) -> str:
    if not s["about"]:
        return ""
    if s["portrait"]:
        art = f'<img src="{esc(s["portrait"])}" alt="Portrait of {esc(s["name"])}" loading="lazy" decoding="async">'
    else:
        art = crest()
    paras = "".join(f"<p>{esc(p)}</p>" for p in s["about"])
    note = f'<p class="note">{esc(s["about_note"])}</p>' if s["about_note"] else ""
    return f"""<section class="section" id="about" aria-labelledby="about-title">
<div class="wrap about-grid">
<figure class="portrait">{art}</figure>
<div>
<h2 id="about-title">About</h2>
{paras}
{note}
</div>
</div>
</section>"""


def videos_section(s: dict) -> str:
    all_videos = ext(s["youtube"] + "/videos", "All videos on YouTube")
    if s["videos"]:
        cards = []
        for v in s["videos"][:6]:
            vid = esc(v["id"])
            published = text(v.get("published"))
            when = f'<time datetime="{esc(published[:10])}">{esc(nice_date(published))}</time>' if published else ""
            cards.append(
                f'<li class="video-card"><a href="https://www.youtube.com/watch?v={vid}" target="_blank" rel="noopener">'
                f'<img src="https://i.ytimg.com/vi/{vid}/mqdefault.jpg" alt="" width="320" height="180" loading="lazy" decoding="async">'
                f'<span class="v-body"><span class="v-title">{esc(v.get("title") or "Untitled")}</span>{when}</span></a></li>'
            )
        content = f'<ul class="video-grid" aria-label="Latest videos">{"".join(cards)}</ul>'
    else:
        # Before the first successful feed refresh, YouTube's own uploads
        # player keeps this section current with no help from us.
        uploads = esc(f'https://www.youtube.com/embed/videoseries?list=UU{s["channel_id"][2:]}&autoplay=1')
        content = f"""<div class="player player-uploads">
<a class="facade" href="{esc(s["youtube"])}/videos" target="_blank" rel="noopener" data-embed="{uploads}" data-title="Latest uploads from {esc(s["name"])}">
<span class="play" aria-hidden="true">{PLAY_ICON}</span><span class="facade-label">Play the latest uploads</span>
</a>
</div>"""
    return f"""<section class="section" id="videos" aria-labelledby="videos-title">
<div class="wrap">
<div class="section-head"><h2 id="videos-title">Latest Videos</h2>{all_videos}</div>
{content}
</div>
</section>"""


def news_section(s: dict) -> str:
    if not s["news"]:
        return ""
    cols = []
    for sec in s["news"]:
        items = []
        for item in sec["items"]:
            meta = [esc(item.get("source") or "")]
            if item.get("published"):
                meta.append(esc(nice_date(item["published"])))
            meta_html = " &middot; ".join(m for m in meta if m)
            items.append(
                f'<li><a href="{esc(item["url"])}" target="_blank" rel="noopener">{esc(item["title"])}</a>'
                f'<span class="news-meta">{meta_html}</span></li>'
            )
        note = f'<p class="news-note">{esc(sec["note"])}</p>' if sec.get("note") else ""
        cols.append(f'<div class="news-col panel"><h3>{esc(sec["title"])}</h3><ol>{"".join(items)}</ol>{note}</div>')
    return f"""<section class="section" id="news" aria-labelledby="news-title">
<div class="wrap">
<div class="section-head"><h2 id="news-title">Town Crier</h2><p>Headlines from around the realm and beyond, refreshed every hour.</p></div>
<div class="news-grid">{"".join(cols)}</div>
<p class="fine">Headlines link to their original publishers.</p>
</div>
</section>"""


def faction_class(entry: dict) -> str:
    faction = text(entry.get("faction")).lower()
    return f" faction-{faction}" if faction in ("alliance", "horde") else ""


def character_card(c: dict, prefix: str) -> str:
    image = find_image(f"characters/{slug(c['name'])}")
    if image:
        art = f'<img src="{prefix}{esc(image)}" alt="{esc(c["name"])}" loading="lazy" decoding="async">'
    else:
        art = crest(c["name"][0].upper())
    line = " ".join(x for x in (f"Level {c['level']}" if c.get("level") else "", c.get("race", ""), c.get("class", "")) if x)
    facts = [(label, c.get(key)) for label, key in (("Faction", "faction"), ("Class", "class"), ("Race", "race"), ("Ruleset", "ruleset"), ("Status", "status"))]
    facts_html = "".join(f"<dt>{label}</dt><dd>{esc(value)}</dd>" for label, value in facts if value)
    return f"""<li class="char-card{faction_class(c)}">
<div class="char-art">{art}</div>
<div class="char-body">
<h3>{esc(c["name"])}</h3>
{f'<p class="char-line">{esc(line)}</p>' if line else ""}
{f'<dl class="facts">{facts_html}</dl>' if facts_html else ""}
</div>
</li>"""


def characters_preview(s: dict) -> str:
    if not s["characters"]:
        return ""
    featured = [c for c in s["characters"] if c.get("featured") is True] or s["characters"]
    cards = "".join(character_card(c, "") for c in featured[:3])
    return f"""<section class="section" id="characters" aria-labelledby="characters-title">
<div class="wrap">
<div class="section-head"><h2 id="characters-title">Characters</h2><a href="characters/">Full roster</a></div>
<ul class="char-grid">{cards}</ul>
</div>
</section>"""


def contact_section(s: dict) -> str:
    if not s["email_code"]:
        return ""
    return f"""<section class="section" id="contact" aria-labelledby="contact-title" data-needs-js hidden>
<div class="wrap narrow center panel">
<h2 id="contact-title">Contact</h2>
<p>Business inquiries, collaborations, or just to say hello.</p>
<a class="btn btn-gold btn-email" data-e="{s["email_code"]}" data-show-address>Email</a>
</div>
</section>"""


# --------------------------------------------------------------- pages

def home_page(s: dict) -> str:
    body = "\n".join(
        part for part in (
            hero(s), support_section(s), about_section(s), videos_section(s),
            news_section(s), characters_preview(s), contact_section(s),
        ) if part
    )
    description = " ".join(x for x in (s["tagline"], s["schedule"]) if x) or s["name"]
    return page(s, title=f'{s["name"]} | Live on YouTube', description=description,
                path="/", prefix="", current="home", body=body)


def characters_page(s: dict) -> str:
    parts = []
    if s["characters"]:
        cards = "".join(character_card(c, "../") for c in s["characters"])
        parts.append(f"""<section class="section first" aria-labelledby="roster-title">
<div class="wrap">
<h2 id="roster-title">Roster</h2>
<ul class="char-grid">{cards}</ul>
</div>
</section>""")
    if s["graveyard"]:
        stones = []
        for g in s["graveyard"]:
            line = " ".join(x for x in (f"Level {g['level']}" if g.get("level") else "", g.get("race", ""), g.get("class", "")) if x)
            stones.append(
                '<li class="tomb">'
                '<p class="tomb-here">Here lies</p>'
                f'<h3>{esc(g["name"])}</h3>'
                + (f'<p class="tomb-line">{esc(line)}</p>' if line else "")
                + (f'<p class="tomb-date">Fell {esc(long_date(g["fell"]))}</p>' if g.get("fell") else "")
                + (f'<p class="tomb-cause">{esc(g["cause"])}</p>' if g.get("cause") else "")
                + (f'<p class="tomb-epitaph">&ldquo;{esc(g["epitaph"])}&rdquo;</p>' if g.get("epitaph") else "")
                + "</li>"
            )
        parts.append(f"""<section class="section graveyard{' first' if not s['characters'] else ''}" id="graveyard" aria-labelledby="graveyard-title">
<div class="wrap">
<div class="section-head"><h2 id="graveyard-title">Graveyard</h2><p>In memory of the Hardcore heroes who fell along the way.</p></div>
<ul class="tomb-grid">{"".join(stones)}</ul>
</div>
</section>""")
    body = f"""<div class="page-head"><div class="wrap"><h1>Characters</h1></div></div>
{"".join(parts)}"""
    return page(s, title=f'Characters | {s["name"]}', description=f'Characters played by {s["name"]}.',
                path="/characters/", prefix="../", current="characters", body=body)


def games_page(s: dict) -> str:
    g = s["games"]
    featured = g.get("featured") or {}
    intro = f'<p class="lede">{esc(g["intro"])}</p>' if text(g.get("intro")) else ""
    feature_html = ""
    if text(featured.get("title")):
        plans = "".join(f"<li>{esc(p)}</li>" for p in featured.get("plans") or [] if text(p))
        feature_html = f"""<article class="game-feature panel">
<p class="badge">Main game</p>
<h2>{esc(featured["title"])}</h2>
{f'<p class="game-date">{esc(featured["released"])}</p>' if text(featured.get("released")) else ""}
{f'<ul class="plan-list">{plans}</ul>' if plans else ""}
<p class="game-links">{ext(s["youtube"] + "/live", "Watch the stream")}</p>
</article>"""
    past = [p for p in g.get("past") or [] if text(p.get("title"))]
    past_html = ""
    if past:
        cards = "".join(
            f'<li class="past-card"><h3>{esc(p["title"])}</h3>'
            + (f'<p>{esc(p["note"])}</p>' if text(p.get("note")) else "")
            + "</li>"
            for p in past
        )
        graveyard_link = ""
        if s["graveyard"]:
            graveyard_link = '<p class="past-more"><a href="../characters/#graveyard">Visit the Graveyard</a></p>'
        past_html = f"""<section class="section" aria-labelledby="past-title">
<div class="wrap">
<h2 id="past-title">Past Versions</h2>
<ul class="past-grid">{cards}</ul>
{graveyard_link}
</div>
</section>"""
    body = f"""<div class="page-head"><div class="wrap"><h1>Games</h1>{intro}</div></div>
<section class="section first"><div class="wrap">{feature_html}</div></section>
{past_html}"""
    return page(s, title=f'Games | {s["name"]}', description=f'What {s["name"]} plays: World of Warcraft: Forever and past versions.',
                path="/games/", prefix="../", current="games", body=body)


def not_found_page(s: dict) -> str:
    body = """<div class="page-head"><div class="wrap narrow center">
<h1>Lost in the Wilds</h1>
<p class="lede">This page does not exist. The road home is this way.</p>
<p><a class="btn btn-gold" href="/">Back to the home page</a></p>
</div></div>"""
    return page(s, title=f'Page not found | {s["name"]}', description="Page not found.",
                path="/404.html", prefix="/", current="", body=body)


# ---------------------------------------------------------------- build

def build() -> None:
    s = read_site()
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC / "assets", OUT / "assets")
    if IMAGES.is_dir():
        shutil.copytree(IMAGES, OUT / "images", ignore=shutil.ignore_patterns(".gitkeep", "*.md"))

    pages = {"index.html": home_page(s), "games/index.html": games_page(s), "404.html": not_found_page(s)}
    if s["has_roster"]:
        pages["characters/index.html"] = characters_page(s)
    for rel, content in pages.items():
        target = OUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    urls = ["/", "/games/"] + (["/characters/"] if s["has_roster"] else [])
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{esc(s['url'] + u)}</loc></url>\n" for u in urls)
        + "</urlset>\n",
        encoding="utf-8",
    )
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {s['url']}/sitemap.xml\n", encoding="utf-8")
    shown = [name for name, on in (
        ("support", s["support"]), ("twitch", s["twitch"]), ("videos", s["videos"]), ("news", s["news"]),
        ("characters", s["characters"]), ("graveyard", s["graveyard"]), ("logo", s["logo"]), ("portrait", s["portrait"]),
    ) if on]
    print(f"Built {len(pages)} pages into _site/. Showing: {', '.join(shown) or 'core sections only'}.")


def main() -> None:
    try:
        build()
    except BuildError as err:
        print(f"Build stopped: {err}", file=sys.stderr)
        print("The live site keeps its last good version until this is fixed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
