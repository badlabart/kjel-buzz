"""Concerts by Country Airplay top-40 artists, nearest to the listening area first.

Tier 1 = Camdenton / Lake of the Ozarks, Springfield, Branson. Tier 2 = Kansas City, St. Louis.
Source: AllEvents city pages (structured event data). Each page shows only its first ~10 events,
so this finds some shows, not all. Found shows are saved in data/concerts.json and stay until the date passes.
Also returns Google News items that tie a top-40 artist to our area (tour stops, sightings, local ties).
"""
import json
import re
from datetime import date, datetime

CITIES = [  # (city name for the card, tier, AllEvents slug)
    ("Camdenton", 1, "camdenton"),
    ("Osage Beach", 1, "osage-beach"),
    ("Springfield", 1, "springfield-mo"),
    ("Branson", 1, "branson"),
    ("Kansas City", 2, "kansas-city"),
    ("St. Louis", 2, "st-louis"),
]
KINDS = ("concerts", "country-music")
AREA = r"Springfield|Camdenton|Lake of the Ozarks|Osage Beach|Branson|Kansas City|St\. Louis|Lebanon, Mo|Missouri"


def _artist_in(text, artists):
    hits = [(r, a) for a, r in artists.items() if re.search(r"\b" + re.escape(a) + r"\b", text, re.I)]
    return min(hits) if hits else None


def _events(c, slug, kind):
    b = c.get(f"https://allevents.in/{slug}/{kind}", headers={"Accept-Encoding": "identity"})
    out = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', b, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for e in data if isinstance(data, list) else [data]:
            if isinstance(e, dict) and "Event" in str(e.get("@type", "")):
                out.append(e)
    return out


def spoken_date(d):
    n = d.day
    suffix = "th" if 11 <= n <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{d.strftime('%A, %B')} {n}{suffix}"


def find_concerts(c, artists):
    path = c.DATA / "concerts.json"
    saved = json.loads(path.read_text()) if path.exists() else []
    today = c.NOW.astimezone(c.CT).date()
    found = {s["key"]: s for s in saved if date.fromisoformat(s["date"]) >= today}
    for city, tier, slug in CITIES:
        for kind in KINDS:
            try:
                events = _events(c, slug, kind)
            except Exception as e:
                c.FAILED.append(f"AllEvents {slug}/{kind} ({str(e)[:30]})")
                continue
            for e in events:
                name = c.text(e.get("name", ""))
                hit = _artist_in(name, artists)
                start = (e.get("startDate") or "")[:10]
                if not hit or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start) or date.fromisoformat(start) < today:
                    continue
                loc = e.get("location") if isinstance(e.get("location"), dict) else {}
                addr = loc.get("address") if isinstance(loc.get("address"), dict) else {}
                venue = c.text(loc.get("name", "")) or "a venue"
                town = c.text(addr.get("addressLocality", "")) or city
                rank, artist = hit
                key = f"{artist}|{start}|{venue}".lower()
                found.setdefault(key, {"key": key, "artist": artist, "rank": rank, "event": name, "venue": venue,
                                       "city": town, "tier": tier, "date": start, "url": e.get("url") or "",
                                       "first_seen": today.isoformat()})
    shows = sorted(found.values(), key=lambda s: (s["tier"], s["date"]))
    path.write_text(json.dumps(shows, indent=1, ensure_ascii=False))
    return shows


def area_news(c, artists):
    """Google News items naming a top-40 artist AND our area: tour stops, on-sales, sightings, local ties."""
    names = sorted(artists, key=lambda a: artists[a])
    out = []
    for i in range(0, len(names), 8):
        group = names[i:i + 8]
        q = ("(" + " OR ".join(f'"{a}"' for a in group) + ") "
             '(Springfield OR Camdenton OR "Lake of the Ozarks" OR "Osage Beach" OR Branson OR "Kansas City" OR "St. Louis" OR Missouri)')
        for it in c.pull(("gn", "music", "Google News", c.gn(q, 30))):
            if (c.NOW - it["ts"]).days > 30 or not re.search(AREA, it["title"]):
                continue
            if not _artist_in(it["title"], {a: artists[a] for a in group}):
                continue
            # Springfield, Ill./Tenn./Mass. and similar are not ours.
            if re.search(r"Springfield,? (Ill|Tenn|Mass|Ohio|Ore|Va|Vt|N\.?J)|Illinois|Tennessee|Massachusetts", it["title"]):
                continue
            it["near"] = 1 if re.search(r"Springfield|Camdenton|Lake of the Ozarks|Osage Beach|Branson|Lebanon", it["title"]) else 2
            out.append(it)
    return out


def sentence(sh, d):
    """On-air line naming the whole bill, so an opener on the chart is never passed off as the headliner."""
    bill = re.sub(r"\s+(in|at)\s+" + re.escape(sh["city"]) + r".*$", "", sh["event"], flags=re.I).strip(" -|")
    if sh["artist"].lower() not in bill.lower():
        bill = f'{bill} with {sh["artist"]}'
    verb = "are coming" if "," in bill and ":" not in bill else "is coming"
    return f'{bill} {verb} to {sh["venue"]} in {sh["city"]} on {spoken_date(d)}.'
