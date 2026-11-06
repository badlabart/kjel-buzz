"""Missouri record leads for Show Prep (Boss 2026-11-06): stories about a Guinness or world record in Missouri or the Ozarks.

Boss liked a UPI odd story (a Missouri dog's Guinness record) and asked for more like it. A Google News search for record
words plus Missouri place names turned up about three on-topic stories a week, but some outlets block our reader (OzarksFirst
returns 403), so no on-air line can be written from the facts. Each one is a LEAD: a headline, its outlet and its age. A jock
opens the story for the facts.

Rolling 7 days in data/leads.json. build.py calls column(); a failed search keeps what is already saved.
Run on its own to see what it would add: python3 -I scripts/leads.py
"""
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import md5
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402  (reuses its tragic / politics / gossip / spam / junk filters)

DATA = Path(__file__).resolve().parent.parent / "data"
PATH = DATA / "leads.json"
KEEP_DAYS = 7
MAX_LEADS = 12
AREA = ('(Missouri OR Ozarks OR Branson OR Springfield OR "Lake of the Ozarks" OR Lebanon OR "Kansas City" OR "St. Louis")')
QUERY = f'("Guinness World Record" OR "Guinness World Records" OR "world record") {AREA} when:7d'
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
# A lead must come from a Missouri outlet or name a Missouri place in the headline ("St. Louis Park" is Minnesota).
LOCAL_OUTLET = re.compile(
    r"ozarksfirst|ky3|kspr|krcg|komu|kmbc|kctv|kshb|ksdk|kmov|fox ?4|lake ?expo|kansas city star|post-dispatch|news-leader|"
    r"missourinet|columbia daily tribune|missourian|kjlu|krms|joplin globe|koam|kttn|st joseph post|business journal|"
    r"lebanon daily record|laclede|lake sun|camdenton|osage beach", re.I)
TITLE_PLACE = re.compile(r"\b(Missouri|Mo\.|Ozarks?|Branson|Kansas City|St\. Louis(?! Park)|Springfield, Mo|Lebanon, Mo|Joplin|"
                         r"Columbia, Mo|Jefferson City|Mizzou)\b")
RECORD = re.compile(r"record|guinness", re.I)  # Google also matches the body text; the headline has to say it
SKIP_SOURCE = re.compile(r"^upi$", re.I)  # UPI Odd News already runs in National; the leads would repeat it
STOP = set("a an the of in on at to for and or with by from after as is are be it its this that new".split())


def _tokens(title):
    return {w for w in re.findall(r"[a-z0-9']+", title.lower()) if w not in STOP}


def _same_story(a, b):
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.6


def _blocked(headline):
    return any(rx.search(headline) for rx in (collect.WEIRD_BLOCK, collect.POLITICS, collect.GOSSIP, collect.SPAM, collect.JUNK))


def search():
    """New leads from Google News: [{id, title, source, url, ts}], newest first."""
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": QUERY, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    body = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read().decode("utf-8", "ignore")
    out = []
    for it in ET.fromstring(body).iter("item"):
        full = html.unescape(it.findtext("title") or "").strip()
        headline, _, source = full.rpartition(" - ")
        if not headline:
            headline, source = full, ""
        if SKIP_SOURCE.search(source) or not RECORD.search(headline) or _blocked(headline):
            continue
        if not (LOCAL_OUTLET.search(source) or TITLE_PLACE.search(headline)):
            continue
        out.append({"id": "R" + md5(headline.encode()).hexdigest()[:6], "title": headline, "source": source or "Google News",
                    "url": it.findtext("link") or "", "ts": parsedate_to_datetime(it.findtext("pubDate")).isoformat()})
    return sorted(out, key=lambda r: r["ts"], reverse=True)


def refresh():
    """Merge today's search into data/leads.json, drop anything older than 7 days, and return the saved list."""
    saved = json.loads(PATH.read_text()) if PATH.exists() else []
    try:
        for new in search():
            if not any(old["id"] == new["id"] or _same_story(old["title"], new["title"]) for old in saved):
                saved.append(new)
    except Exception as e:  # a failed search keeps what is saved
        print(f"leads: search failed ({str(e)[:60]}), keeping {len(saved)} saved", file=sys.stderr)
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    saved = [r for r in saved if datetime.fromisoformat(r["ts"]) >= cutoff]
    saved = sorted(saved, key=lambda r: r["ts"], reverse=True)[:MAX_LEADS]
    PATH.write_text(json.dumps(saved, indent=1, ensure_ascii=False))
    return saved


def column():
    """Show Prep column: Missouri record leads, headline only (no on-air line), newest first."""
    cards = [{"id": r["id"], "kind": "lead", "title": r["title"], "line": "", "city": "", "source": r["source"], "url": r["url"],
              "ts": r["ts"], "signal": ""} for r in refresh()]
    return {"key": "leads", "name": "Records (MO)", "cards": cards}


if __name__ == "__main__":
    for r in refresh():
        print(r["ts"][:10], "|", r["source"], "|", r["title"][:110])
