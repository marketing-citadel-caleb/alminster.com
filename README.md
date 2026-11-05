# alminster.com

The streaming hub for **Alminster of Azeroth**. Free hosting on GitHub Pages, no routine upkeep.

- **Changes you make** live in a few small files (`data/` and `images/`). Edit one, commit, and the site rebuilds itself in about two minutes.
- **Changes that happen on their own:** latest videos and the Town Crier headlines refresh every hour through a GitHub Action.
- **Anything without data stays hidden.** Leave a link empty and its button, section or menu item simply is not there.
- **A typo can't break the live site.** If a data file has a mistake, the build stops and the site stays on its last good version. The error message says which line to fix.

## How to edit (no tools needed)

1. Open the file on github.com (for example `data/site.json`).
2. Click the pencil icon, make the change, then click **Commit changes**.
3. Wait about two minutes and refresh alminster.com.

If the change does not show up, open the **Actions** tab. A red X means the build stopped; click it to see the message (usually a missing comma or quote).

**JSON tips:** text goes inside straight double quotes `"like this"`, and items in a list are separated by commas, with no comma after the last one.

## Everyday tasks (each is one file)

### Turn on Ko-fi, Patreon or Twitch

File: `data/site.json`. Paste the full link between the quotes:

```json
"twitch": "https://www.twitch.tv/yourchannel",
"kofi": "https://ko-fi.com/yourpage",
"patreon": "https://www.patreon.com/yourpage",
```

- **Ko-fi or Patreon** turns on the Support section, the "Support the Stream" button at the top (it replaces "Subscribe on YouTube"), the Support menu item and the footer links.
- **Twitch** adds a "Watch on Twitch" option under the player and a footer link.

To turn one off again, empty the quotes: `"kofi": ""`.

### Add a character

File: `data/characters.json`. Add an entry inside the `characters` list:

```json
{
  "characters": [
    {
      "name": "Brightwind",
      "faction": "Alliance",
      "race": "Human",
      "class": "Paladin",
      "ruleset": "PvP",
      "status": "Main",
      "level": 60,
      "featured": true
    }
  ],
  "graveyard": []
}
```

- Only `name` is required. Any field you leave out is simply not shown.
- `featured: true` puts the card on the home page (up to 3). If none are featured, the first three show.
- The Characters page and the home page preview appear as soon as the first character is added.
- For a second character, add a comma after the first entry's closing `}` and paste another `{ ... }`.

### Add a Graveyard entry (fallen Hardcore character)

Same file, inside the `graveyard` list:

```json
"graveyard": [
  {
    "name": "Grimtooth",
    "race": "Dwarf",
    "class": "Hunter",
    "level": 41,
    "fell": "2025-03-14",
    "cause": "Ambushed in a mountain pass",
    "epitaph": "He saw the patrol too late."
  }
]
```

`fell` is a date written as year-month-day. Everything except `name` is optional.

### Swap in the logo and photos

Upload a file into the `images/` folder with one of these exact names (on github.com: open `images/`, then **Add file > Upload files**). No other edit is needed.

| File | Where it shows |
| --- | --- |
| `logo.png` (or .svg, .webp) | Replaces the text wordmark on the home page and in the header |
| `portrait.jpg` | The About section (otherwise a crest emblem) |
| `stream.jpg` | Background of the "Play the stream here" panel |
| `social.png` | Preview image when the site is shared (1200 x 630) |
| `characters/brightwind.jpg` | That character's card (character name in lowercase) |

Keep images under about 300 KB so the site stays fast. To remove one, delete the file.

### Change the wording

`data/site.json` holds the tagline, the schedule line, the About paragraphs, the support line and the Games page text.

### Change the headline sources

`data/feeds.json` lists the feeds behind the three Town Crier columns (WoW: Forever, World, Markets). Any RSS feed URL works. Add a publisher's name to `hideSources` to keep it out (useful for gold-selling spam sites that show up in search results).

World and Markets draw on outlets known for straight, non-partisan reporting (Reuters, BBC News, DW and AP), with `"mixSources": true` so the outlets take turns and no single one fills a column. Without it, a column that has several feeds simply shows the newest headlines first.

## What runs automatically

**Hourly refresh** (`.github/workflows/site.yml`). Every hour it fetches Damian's latest YouTube uploads and the headlines, rebuilds the site and publishes it. It also runs whenever a file is committed, and you can run it by hand from **Actions > Build and deploy > Run workflow**.

- **YouTube's RSS feed has outages.** It was returning errors for every channel on launch day. When it fails, the last saved video list stays up. Until the first successful fetch, Latest Videos shows YouTube's own "latest uploads" player, which is always current.
- **Optional backup source:** add a YouTube Data API key and the refresh uses it whenever RSS is down. In Google Cloud Console, create a project, enable **YouTube Data API v3**, create an API key and restrict it to that API. Then in GitHub go to **Settings > Secrets and variables > Actions > New repository secret**, name it `YOUTUBE_API_KEY` and paste the key. The key is used only inside the Action and never reaches the website.
- **Staying switched on:** GitHub pauses hourly jobs in repositories with no commits for 60 days. The workflow makes a one-line commit (`.github/keepalive`) whenever the repository has been quiet for 45 days, so this never happens.

**Blizzard character sync** (`.github/workflows/character-sync.yml`) is included but switched off, because Blizzard has not yet published the profile API for WoW: Forever. The site does not depend on it. To switch it on later:

1. Create an API client at develop.battle.net.
2. Add repository secrets `BLIZZARD_CLIENT_ID` and `BLIZZARD_CLIENT_SECRET`.
3. Add repository variables `BLIZZARD_REGION` (for example `us`), `BLIZZARD_PROFILE_NAMESPACE` (the Forever namespace Blizzard publishes) and `CHARACTER_SYNC_ENABLED` set to `true`.
4. Give each character an `"armory": { "realm": "realm-slug" }` field.
5. Uncomment the `schedule` lines in the workflow file.

It fills in level, race, class and faction. Name, ruleset, status and featured are never overwritten.

## Domain and DNS

DNS for alminster.com is managed at Squarespace Domains. **Email runs on Google Workspace and its records must stay exactly as they are.**

Remove (Squarespace's default website records, which show the current "Coming Soon" page):

| Type | Host | Value |
| --- | --- | --- |
| A | @ | 198.185.159.144 |
| A | @ | 198.185.159.145 |
| A | @ | 198.49.23.144 |
| A | @ | 198.49.23.145 |
| HTTPS | @ | `1 . alpn=h2,http/1.1 ipv4hint=...` |
| CNAME | www | ext-sq.squarespace.com |

Add:

| Type | Host | Value |
| --- | --- | --- |
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| AAAA | @ | 2606:50c0:8000::153 |
| AAAA | @ | 2606:50c0:8001::153 |
| AAAA | @ | 2606:50c0:8002::153 |
| AAAA | @ | 2606:50c0:8003::153 |
| CNAME | www | marketing-citadel-caleb.github.io |
| TXT | \_github-pages-challenge-marketing-citadel-caleb | (recommended, blocks domain takeover: GitHub profile picture > Settings > Pages > Add a domain shows the value) |

Do not touch:

| Type | Host | Value |
| --- | --- | --- |
| MX | @ | smtp.google.com (priority 1) |
| TXT | @ | v=spf1 include:\_spf.google.com ~all |
| TXT | google.\_domainkey | v=DKIM1; k=rsa; p=... |
| CNAME | \_domainconnect | \_domainconnect.domains.squarespace.com |

Then, in the GitHub repository: **Settings > Pages > Custom domain**, enter `alminster.com`, save, and tick **Enforce HTTPS** once GitHub has issued the certificate (usually within an hour). Both `alminster.com` and `www.alminster.com` will then serve the site over HTTPS, and www redirects to the main address.

**Email check after the DNS change:** send a message from an outside address to alminster@alminster.com (tests receiving), then reply from alminster@alminster.com (tests sending). Both should arrive normally.

Optional, separate from hosting: the domain has no DMARC record. Adding one later (a TXT record at `_dmarc`) would help deliverability.

## Working on the code

Python 3 is the only requirement (standard library, no packages).

```
python scripts/fetch_feeds.py   # refresh data/videos.json and data/news.json
python scripts/build.py         # build the site into _site/
python -m http.server 8000 -d _site
```

| Path | What it is |
| --- | --- |
| `data/site.json` | Name, links, wording |
| `data/characters.json` | Roster and Graveyard |
| `data/feeds.json` | Headline sources |
| `data/videos.json` | Latest videos (written by the hourly Action) |
| `images/` | Logo and photos, picked up by file name |
| `src/site.css`, `src/assets/` | Styles, script, font (Cinzel, SIL Open Font License), emblem |
| `scripts/build.py` | Builds the pages from the data |
| `scripts/fetch_feeds.py` | Fetches videos and headlines |
| `scripts/sync_characters.py` | Blizzard sync (off) |

The look is original: no Blizzard logos, artwork or trademarked imagery. World of Warcraft is a trademark of Blizzard Entertainment, Inc.
