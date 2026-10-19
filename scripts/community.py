"""Community congratulations: school districts, chambers and local businesses in the core listening area.

Called from collect.py. Every item comes back as a Local item with its town already set, so the
Lebanon / rest-of-area split works without guessing. Only posts that read like an accomplishment,
honor or milestone are kept.
"""
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# Apptegy (Thrillshare) school sites: their Live Feed carries the district's own social posts, with dates.
APPTEGY = [
    ("Waynesville R-VI Schools", "www.waynesville.k12.mo.us", "Waynesville"),
    ("Gasconade C-4 Schools", "www.gasconadec4.org", "Laclede County"),
    ("Crocker R-II Schools", "www.crockerschools.org", "Crocker"),
    ("Fordland R-III Schools", "www.fordlandschools.org", "Fordland"),
    ("School of the Osage", "www.osage.k12.mo.us", "Lake Ozark"),
    ("Iberia R-V Schools", "www.iberia.k12.mo.us", "Iberia"),
]
# Finalsite news boards (no dates on the page, so first-seen date stands in). Lebanon R-3 lives in collect.py.
FINALSITE = [
    ("Seymour R-II Schools", "https://www.seymourschools.org/district-infomation/news-announcements", "Seymour"),
]
# Plain RSS feeds: (name, url, town, keep_all). keep_all=False keeps only accomplishment-style posts.
RSS = [
    ("Richland R-IV Schools", "https://www.richland.k12.mo.us/apps/news/news_rss.jsp", "Richland", False),
    ("Camdenton Area Chamber", "https://camdentonchamber.com/feed/", "Camdenton", False),
    ("Lake West Chamber", "https://www.lakewestchamber.com/feed/", "Lake of the Ozarks", False),
    ("Mountain Grove Chamber", "https://mountaingrovechamber.com/feed/", "Mountain Grove", False),
    ("Laclede Electric Cooperative", "https://lacledeelectric.com/feed/", "Laclede County", False),
]
MERCY = "https://www.mercy.net/newsroom/"
LIVE_DAYS = 21  # how far back to read feeds; collect.py applies the real freshness rules

ACCOMPLISH = re.compile(
    r"congrat\w*|proud|celebrat\w*|recogni[sz]\w*|honou?r\w*|award\w*|named|selected|scholarships?|"
    r"of the (week|month|year)|champion\w*|state (qualifier|champion|title|finals?)|qualif\w*|"
    r"all-(state|district|conference|region)|placed|first place|1st place|medal\w*|record|"
    r"anniversar\w*|ribbon[- ]cutting|grand opening|milestone|retir\w*|graduat\w*|promot\w*|"
    r"semifinalists?|finalists?|eagle scout|signs? with|commit\w* to|wins?\b|won\b|achiev\w*|excellen\w*|"
    r"top \d+|best\b|grant|donat\w*", re.I)


def _text(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _title_from(text):
    first = next((ln.strip() for ln in text.split("\n") if len(ln.strip()) > 15), text.strip())
    first = re.split(r"(?<=[.!?])\s", first)[0]
    return first[:140]


def _item(c, source, title, url, ts, desc, town):
    return {"col": "local", "title": title, "url": url, "source": source, "ts": ts, "desc": desc[:3000],
            "gn": False, "town": town, "tier": 0 if town == "Lebanon" else 1, "community": True}


def apptegy(c):
    out = []
    for name, host, town in APPTEGY:
        page = f"https://{host}/live-feed"
        try:
            b = c.get(page)
            sid = re.search(r"api/v2/s/(\d+)/live_feeds", b)
            if not sid:
                c.FAILED.append(f"{name} (no live feed found)")
                continue
            d = json.loads(c.get(f"https://thrillshare-cmsv2.services.thrillshare.com/api/v2/s/{sid.group(1)}/live_feeds?page_no=1",
                                 headers={"Accept": "application/json"}))
        except Exception as e:
            c.FAILED.append(f"{name} ({str(e)[:40]})")
            continue
        for p in d.get("live_feeds", []):
            text = _text(p.get("status", ""))
            try:
                ts = datetime.fromisoformat(p["time"])
            except (KeyError, ValueError):
                continue
            if (c.NOW - ts) > timedelta(days=LIVE_DAYS) or not ACCOMPLISH.search(text):
                continue
            out.append(_item(c, name, _title_from(text), page, ts, text.replace("\n", " "), town))
    return out


def finalsite(c):
    path = c.DATA / "finalsite_seen.json"
    seen = json.loads(path.read_text()) if path.exists() else {}
    out = []
    for name, page, town in FINALSITE:
        try:
            b = c.get(page)
        except Exception as e:
            c.FAILED.append(f"{name} ({str(e)[:40]})")
            continue
        first_run = not any(k.startswith(page) for k in seen)
        for n, (slug, title) in enumerate(re.findall(r'class="fsPostLink" data-slug="([^"]+)"[^>]*>(.*?)</a>', b, re.S)):
            key = f"{page}|{slug}"
            if key not in seen:
                seen[key] = (c.NOW if not first_run or n < 3 else c.NOW - timedelta(days=60)).isoformat()
            title = _text(title)
            if ACCOMPLISH.search(title):
                out.append(_item(c, name, title, page, datetime.fromisoformat(seen[key]), "", town))
    path.write_text(json.dumps(seen, indent=0))
    return out


def rss(c):
    out = []
    for name, url, town, keep_all in RSS:
        try:
            root = ET.fromstring(c.get(url).lstrip())
        except Exception as e:
            c.FAILED.append(f"{name} ({str(e)[:40]})")
            continue
        for it in root.findall(".//item"):
            title = _text(it.findtext("title") or "")
            desc = _text(it.findtext("description") or "").replace("\n", " ")
            try:
                import email.utils
                ts = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
            except (TypeError, ValueError):
                continue
            if (c.NOW - ts) > timedelta(days=LIVE_DAYS):
                continue
            if not keep_all and not ACCOMPLISH.search(f"{title} {desc[:200]}"):
                continue
            here = "Lebanon" if re.search(r"\bLebanon\b", f"{title} {desc[:200]}") and town == "Laclede County" else town
            out.append(_item(c, name, title, (it.findtext("link") or "").strip(), ts, desc, here))
    return out


def mercy(c):
    """Mercy newsroom: only Mercy Hospital Lebanon items. The date is in the link."""
    try:
        b = c.get(MERCY)
    except Exception as e:
        c.FAILED.append(f"Mercy newsroom ({str(e)[:40]})")
        return []
    out = []
    for link in dict.fromkeys(re.findall(r'href="(/newsroom/(\d{4}-\d{2}-\d{2})/[^"]*lebanon[^"]*)"', b, re.I)):
        path, day = link
        ts = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        if (c.NOW - ts) > timedelta(days=LIVE_DAYS):
            continue
        slug = path.rstrip("/").split("/")[-1]
        title = re.sub(r"\s+", " ", slug.replace("-", " ")).strip().capitalize()
        out.append(_item(c, "Mercy Hospital Lebanon", title, "https://www.mercy.net" + path, ts, "", "Lebanon"))
    return out


def collect(c):
    items = []
    for fn in (apptegy, finalsite, rss, mercy):
        items += fn(c)
    return items
