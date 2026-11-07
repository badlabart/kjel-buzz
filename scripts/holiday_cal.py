"""Holidays for Show Prep (Boss 2026-11-06): the US holidays and the Missouri / Ozarks days that matter on air.

Two jobs.
1. The calendar. Every date is computed from its rule, so nothing here goes stale. names_on("2026-11-11") -> "VETERANS DAY".
   page.py shows that name in red on every dated card, and in the forecast, whose date is a holiday. The Date search uses
   table() to say "TUESDAY 11/11 IS VETERANS DAY" at the top, so a jock voice tracking ahead is told.
2. The Holidays column: one card per holiday in the next 30 days, and under each holiday that is 14 days or less away, the local
   news about it (Google News, Missouri outlets or Missouri place names only), headline only, like the Records (MO) leads.

Federal + Missouri status is from 5 U.S.C. 6103 and RSMo 9.010 (read 2026-11-06). Super Bowl dates cannot be computed:
add each year to SUPER_BOWL once the NFL sets it. Super Bowl LXI is Feb 14, 2027 (several sources, one calls it tentative).

Run on its own to see the next 90 days and what it would add: python3 -I scripts/holiday_cal.py
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import md5
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402  (its tragic / politics / gossip / spam / junk filters and the Central time zone)
import leads  # noqa: E402  (same story test, same filters, same User-Agent)

DATA = Path(__file__).resolve().parent.parent / "data"
PATH = DATA / "holiday_news.json"
SHOW_DAYS = 30      # a holiday card shows this many days ahead
NEWS_DAYS = 14      # local news is searched for holidays this close
MAX_PER_HOLIDAY = 5
KEEP_DAYS = 21      # a saved story older than this is dropped
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
FED_MO = "FEDERAL + MISSOURI HOLIDAY"
MO = "MISSOURI HOLIDAY"
SUPER_BOWL = {2027: date(2027, 2, 14)}
# Boss (2026-11-07): holidays reach the live Show Prep at the Monday 11/9 refresh, not before. Until then every public function here is
# switched off, so a push on Saturday or Sunday carries no holiday markup. Once Monday has passed this line does nothing.
LIVE_FROM = date(2026, 11, 9)


def live(today=None):
    return (today or datetime.now(collect.CT).date()) >= LIVE_FROM


def nth(y, m, wd, n):
    first = date(y, m, 1)
    return first + timedelta(days=(wd - first.weekday()) % 7 + 7 * (n - 1))


def last(y, m, wd):
    end = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return end - timedelta(days=(end.weekday() - wd) % 7)


def easter(y):  # the anonymous Gregorian computus
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return date(y, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)


# name, date rule, status, news search ("" = none), words a headline must hold
RULES = [
    ("NEW YEAR'S DAY", lambda y: date(y, 1, 1), FED_MO, '"New Year\'s Day" OR "New Year\'s"', r"new year"),
    ("MARTIN LUTHER KING JR. DAY", lambda y: nth(y, 1, MON, 3), FED_MO, '"MLK Day" OR "Martin Luther King"', r"\bMLK\b|martin luther king"),
    ("LINCOLN'S BIRTHDAY", lambda y: date(y, 2, 12), MO, "", ""),
    ("VALENTINE'S DAY", lambda y: date(y, 2, 14), "", "Valentine", r"valentine"),
    ("SUPER BOWL SUNDAY", lambda y: SUPER_BOWL.get(y), "", '"Super Bowl"', r"super bowl"),
    ("PRESIDENTS' DAY", lambda y: nth(y, 2, MON, 3), FED_MO, '"Presidents Day" OR "Presidents\' Day"', r"presidents.? day"),
    ("ST. PATRICK'S DAY", lambda y: date(y, 3, 17), "", '"St. Patrick" OR "Saint Patrick"', r"patrick"),
    ("GOOD FRIDAY", lambda y: easter(y) - timedelta(days=2), "", '"Good Friday"', r"good friday"),
    ("EASTER", easter, "", "Easter", r"easter"),
    ("TRUMAN DAY", lambda y: date(y, 5, 8), MO, '"Truman Day"', r"truman day"),
    ("MOTHER'S DAY", lambda y: nth(y, 5, SUN, 2), "", '"Mother\'s Day"', r"mother.?s day"),
    ("ARMED FORCES DAY", lambda y: nth(y, 5, SAT, 3), "", '"Armed Forces Day"', r"armed forces day"),
    ("MEMORIAL DAY", lambda y: last(y, 5, MON), FED_MO, '"Memorial Day"', r"memorial day"),
    ("FATHER'S DAY", lambda y: nth(y, 6, SUN, 3), "", '"Father\'s Day"', r"father.?s day"),
    ("JUNETEENTH", lambda y: date(y, 6, 19), FED_MO, "Juneteenth", r"juneteenth"),
    ("INDEPENDENCE DAY", lambda y: date(y, 7, 4), FED_MO, '"Fourth of July" OR "July 4" OR "Independence Day"',
     r"fourth of july|july 4|independence day|fireworks"),
    ("LABOR DAY", lambda y: nth(y, 9, MON, 1), FED_MO, '"Labor Day"', r"labor day"),
    ("PATRIOT DAY", lambda y: date(y, 9, 11), "", '"Patriot Day" OR "9/11" OR "September 11"', r"patriot day|9/11|sept(ember|\.)? 11"),
    ("COLUMBUS DAY", lambda y: nth(y, 10, MON, 2), FED_MO, '"Columbus Day" OR "Indigenous Peoples"', r"columbus day|indigenous peoples"),
    ("HALLOWEEN", lambda y: date(y, 10, 31), "", 'Halloween OR "trick-or-treat"', r"halloween|trick.or.treat"),
    ("VETERANS DAY", lambda y: date(y, 11, 11), FED_MO, '"Veterans Day"', r"veteran"),
    ("THANKSGIVING", lambda y: nth(y, 11, THU, 4), FED_MO, "Thanksgiving", r"thanksgiving"),
    ("BLACK FRIDAY", lambda y: nth(y, 11, THU, 4) + timedelta(days=1), "", '"Black Friday"', r"black friday"),
    ("PEARL HARBOR REMEMBRANCE DAY", lambda y: date(y, 12, 7), "", '"Pearl Harbor"', r"pearl harbor"),
    ("CHRISTMAS EVE", lambda y: date(y, 12, 24), "", '"Christmas Eve"', r"christmas eve"),
    ("CHRISTMAS DAY", lambda y: date(y, 12, 25), FED_MO, "Christmas", r"christmas(?! eve)"),
    ("NEW YEAR'S EVE", lambda y: date(y, 12, 31), "", '"New Year\'s Eve"', r"new year.?s eve"),
]

AREA = ('(Missouri OR Ozarks OR Branson OR Springfield OR "Lake of the Ozarks" OR Lebanon OR Waynesville OR '
        '"Fort Leonard Wood" OR Camdenton OR "Osage Beach")')
# A story counts when a Missouri outlet ran it or the headline names a Missouri place. "Lebanon", "Waynesville" and "Springfield"
# alone are not enough: there is a Lebanon in Indiana and Oregon, a Waynesville in North Carolina (The Mountaineer) and a
# Springfield in Massachusetts.
LOCAL_OUTLET = re.compile(leads.LOCAL_OUTLET.pattern + r"|missouri|mizzou|daily guide|kfvs|kzrg|417 mag|semissourian|"
                          r"kirksville|perryville|park hills|kolr|kmiz|ksmu|klrt|kwto|ktts", re.I)
TITLE_PLACE = re.compile(leads.TITLE_PLACE.pattern + r"|Fort Leonard Wood|Waynesville, Mo|St\. Robert|Saint Robert|Lake of the Ozarks|"
                         r"Osage Beach|Camdenton|Lake Ozark|Mid-Missouri|Laclede County|Pulaski County, Mo", re.I)


NEAR = re.compile(r"lebanon|laclede|waynesville|fort leonard wood|st\. robert|saint robert|pulaski|lake of the ozarks|lake ozark|"
                  r"osage beach|camdenton|camden county|marshfield|daily guide|lake ?expo|krms|kjel", re.I)
OZARKS = re.compile(r"springfield|branson|ozarks|joplin|ky3|kspr|kolr|417|news-leader|koam|kzrg", re.I)


def _tier(r):
    text = r["title"] + " " + r["source"]
    return 0 if NEAR.search(text) else 1 if OZARKS.search(text) else 2


def holidays_in(start, end):
    """[(date, name, status, search, words)] from start to end, soonest first (both ends included)."""
    out = []
    for y in range(start.year, end.year + 1):
        for name, rule, status, search, words in RULES:
            d = rule(y)
            if d and start <= d <= end:
                out.append((d, name, status, search, words))
    return sorted(out, key=lambda h: (h[0], h[1]))


def names_on(iso):
    """"VETERANS DAY", or "VALENTINE'S DAY · SUPER BOWL SUNDAY" when two share a date, or "" on an ordinary day."""
    if not live():
        return ""
    d = date.fromisoformat(iso)
    return " · ".join(h[1] for h in holidays_in(d, d))


def table(today=None):
    """{iso: name} for this year and the next two: the Date search uses it in the browser."""
    today = today or datetime.now(collect.CT).date()
    if not live(today):
        return {}
    out = {}
    for d, name, *_ in holidays_in(date(today.year, 1, 1), date(today.year + 2, 12, 31)):
        out[d.isoformat()] = (out[d.isoformat()] + " · " if d.isoformat() in out else "") + name
    return out


def search(search_terms, words):
    """Local stories about one holiday from Google News: [{id, title, source, url, ts}], newest first."""
    q = f"({search_terms}) {AREA} when:{NEWS_DAYS}d"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    body = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": leads.UA}), timeout=30).read().decode("utf-8", "ignore")
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_DAYS)
    out = []
    for it in ET.fromstring(body).iter("item"):
        full = html.unescape(it.findtext("title") or "").strip()
        headline, _, source = full.rpartition(" - ")
        if not headline:
            headline, source = full, ""
        ts = parsedate_to_datetime(it.findtext("pubDate"))
        if ts < cutoff or not re.search(words, headline, re.I) or leads._blocked(headline):
            continue
        if not (LOCAL_OUTLET.search(source) or TITLE_PLACE.search(headline)):
            continue
        out.append({"id": "H" + md5(headline.encode()).hexdigest()[:6], "title": headline, "source": source or "Google News",
                    "url": it.findtext("link") or "", "ts": ts.isoformat()})
    return sorted(out, key=lambda r: r["ts"], reverse=True)


def refresh(today=None):
    """Merge today's searches into data/holiday_news.json (each row carries its holiday and date), drop rows for holidays that
    have passed or stories older than 21 days, and return the saved list. A failed search keeps what is saved."""
    today = today or datetime.now(collect.CT).date()
    saved = json.loads(PATH.read_text()) if PATH.exists() else []
    for d, name, status, terms, words in holidays_in(today, today + timedelta(days=NEWS_DAYS)):
        if not terms:
            continue
        try:
            new = search(terms, words)
            time.sleep(1)
        except Exception as e:
            print(f"holidays: {name} search failed ({str(e)[:60]})", file=sys.stderr)
            continue
        mine = [o for o in saved if o["hol"] == name and o["date"] == d.isoformat()]
        saved = [o for o in saved if o not in mine]
        for r in new:
            if not any(o["id"] == r["id"] or leads._same_story(o["title"], r["title"]) for o in mine):
                mine.append(dict(r, hol=name, date=d.isoformat()))
        # Boss's listening area first (Lebanon is the goal), then the rest of the Ozarks, then elsewhere in Missouri; newest within each
        mine.sort(key=lambda o: (_tier(o), -datetime.fromisoformat(o["ts"]).timestamp()))
        saved += mine[:MAX_PER_HOLIDAY]
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    saved = [r for r in saved if date.fromisoformat(r["date"]) >= today and datetime.fromisoformat(r["ts"]) >= cutoff]
    PATH.write_text(json.dumps(saved, indent=1, ensure_ascii=False))
    return saved


def column(today=None):
    """Show Prep column: a card for each holiday in the next 30 days, local stories under the ones 14 days or less away."""
    today = today or datetime.now(collect.CT).date()
    if not live(today):
        return {"key": "holidays", "name": "Holidays", "cards": []}
    news = refresh(today)
    cards = []
    for d, name, status, *_ in holidays_in(today, today + timedelta(days=SHOW_DAYS)):
        iso = d.isoformat()
        cards.append({"kind": "holiday", "title": name, "badge": status, "line": name, "city": "", "source": "", "url": "", "ts": None,
                      "signal": "", "date": iso, "when_label": d.strftime("%a, %b %-d").upper()})
        for r in (r for r in news if r["hol"] == name and r["date"] == iso):
            cards.append({"id": r["id"], "kind": "holnews", "title": r["title"], "line": "", "city": "", "source": r["source"],
                          "url": r["url"], "ts": r["ts"], "signal": "", "date": iso, "hol": name,
                          "when_label": d.strftime("%a, %b %-d").upper()})
    return {"key": "holidays", "name": "Holidays", "cards": cards}


if __name__ == "__main__":
    t = datetime.now(collect.CT).date()
    for d, name, status, *_ in holidays_in(t, t + timedelta(days=90)):
        print(d.strftime("%a %Y-%m-%d"), "|", name, "|", status or "-")
    print("--- local stories")
    for r in refresh(t):
        print(r["date"], r["hol"], "|", r["source"], "|", r["title"][:100])
