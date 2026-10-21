"""Humor candidates: this week's top-voted clean jokes from Reddit, plus weekly funniest-posts roundups.

Called from collect.py. Reddit allows about one pull a morning, so all joke boards come in one combined request.
Freshness guards: skip anything close to a known classic (icanhazdadjoke list) and anything the board already showed.
"""
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

A = "{http://www.w3.org/2005/Atom}"
REDDIT = "https://www.reddit.com/r/dadjokes+cleanjokes+oneliners+Jokes+Showerthoughts/top/.rss?t=day&limit=100"
LIST_FEEDS = [
    ("HuffPost", "https://www.huffpost.com/section/comedy/feed"),
    ("Pleated Jeans", "https://pleated-jeans.com/feed/"),
    ("Cheezburger", "https://cheezburger.com/rss"),
]
LIST_Q = '"funniest tweets" OR "funniest posts" OR "funniest parenting" OR "hilarious tweets"'
MAX_JOKE_CHARS = 170  # Boss (2026-10-19): Humor must read in ONE LINE, no click needed
DIRTY = re.compile(
    r"\b(sex\w*|penis|vagina|dick|cock|boobs?|tits?|ass|asses|asshole|fuck\w*|shit\w*|bitch\w*|porn\w*|naked|nude|"
    r"horny|orgasm|condoms?|viagra|blow ?jobs?|whores?|sluts?|hookers?|strippers?|erection|testicl\w*|balls|"
    r"weed|stoned|cocaine|meth|hitler|nazis?|rape\w*|virgin\w*|wank\w*|masturbat\w*|panties|thong|nipples?|"
    r"genital\w*|pubes?|bang(ed|ing)?|screw(ed|ing)?|69|lesbian|gay|tranny|retard\w*|n-word|nsfw|cum|"
    r"autoerotic|asphyxia\w*|piss\w*|cheat\w*|affair|mistress|dildo|kinky|bdsm|hooters|two girls|one cup|"
    r"white (people|guys?)|black (people|guys?)|cracka\w*|redneck|mexicans?|asians?|antidepressants?|lawyers? charge)\b", re.I)
FUNNY_LIST = re.compile(r"funn|hilar|laugh|joke|meme|tweet|posts|reviews|comic|lol\b", re.I)
META = re.compile(r"years ago today|repost|\bmods?\b|subreddit|r/|upvote|karma|this sub", re.I)


def jaccard(a, b):
    return len(a & b) / max(1, len(a | b))


def classics(c):
    """~744 well-worn dad jokes, fetched once and cached."""
    path = c.DATA / "classic_jokes.json"
    if path.exists():
        return json.loads(path.read_text())
    out = []
    try:
        for page in range(1, 40):
            d = json.loads(c.get(f"https://icanhazdadjoke.com/search?limit=30&page={page}",
                                 headers={"Accept": "application/json", "User-Agent": "KJEL Buzz Report"}))
            out += [j["joke"] for j in d["results"]]
            if page >= d["total_pages"]:
                break
            time.sleep(1)
        path.write_text(json.dumps(out, indent=0, ensure_ascii=False))
    except Exception as e:
        c.FAILED.append(f"classic joke list ({str(e)[:40]})")
    return out


def shown(c, before_today=False):
    """Jokes already on the board as {"text", "day"}. Older entries were plain strings (aired before 2026-10-19)."""
    path = c.DATA / "humor_shown.json"
    rows = json.loads(path.read_text()) if path.exists() else []
    rows = [r if isinstance(r, dict) else {"text": r, "day": "2026-10-18"} for r in rows]
    today = c.NOW.astimezone(c.CT).date().isoformat()
    return [r for r in rows if not before_today or r["day"] < today]


def reddit_jokes(c):
    try:
        root = ET.fromstring(c.get(REDDIT))
    except Exception as e:
        c.FAILED.append(f"Reddit jokes ({str(e)[:40]})")
        return [], {}
    old = [c.words(j) for j in classics(c)]
    seen = [c.words(r["text"]) for r in shown(c, before_today=True)]  # a same-day rebuild may reuse today's jokes
    out, dropped = [], {}
    for rank, en in enumerate(root.findall(A + "entry"), 1):
        cat = en.find(A + "category")
        sub = "r/" + cat.get("term") if cat is not None and cat.get("term") else "Reddit"
        setup = c.text(en.findtext(A + "title") or "")
        md = re.search(r'<div class="md">(.*?)</div>', html.unescape(en.findtext(A + "content") or ""), re.S)
        punch = c.text(md.group(1)) if md else ""
        if punch in ("[removed]", "[deleted]"):
            punch = ""
        link = en.find(A + "link").get("href") if en.find(A + "link") is not None else ""
        stamp = en.findtext(A + "published") or en.findtext(A + "updated") or ""
        try:
            ts = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            ts = c.NOW
        joke = f"{setup} {punch}".strip()
        w = c.words(joke)
        why = None
        if len(joke) > MAX_JOKE_CHARS:
            why = "too long for a break"
        elif DIRTY.search(joke):
            why = "not clean"
        elif c.TRAGIC.search(joke) or c.POLITICS.search(joke) or c.ICE.search(joke):
            why = "downer/politics"
        elif META.search(joke) or c.SPAM.search(joke):
            why = "meta/spam"
        elif w and any(jaccard(w, o) >= 0.6 for o in old):
            why = "classic (overused)"
        elif w and any(jaccard(w, s) >= 0.7 for s in seen):
            why = "already shown"
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        out.append({"col": "humor", "kind": "joke", "title": setup, "punch": punch, "source": sub, "url": link,
                    "ts": ts, "desc": "", "gn": False, "score": 100 - rank,
                    "signal": f"#{rank} of today's 100 top-voted Reddit jokes and one-liners"})
    return out, dropped


def roundups(c):
    items = []
    for label, url in LIST_FEEDS:
        items += c.pull(("feed", "humor", label, url))
    items += c.pull(("gn", "humor", "Google News", c.gn(LIST_Q, 7)))
    keep = []
    for it in items:
        t = it["title"]
        if (c.NOW - it["ts"]) > timedelta(days=7) or not FUNNY_LIST.search(t):
            continue
        if DIRTY.search(t) or c.TRAGIC.search(t) or c.POLITICS.search(t) or c.ICE.search(t) or c.GOSSIP.search(t):
            continue
        keep.append(it)
    out = c.cluster(keep)
    for it in out:
        it["kind"] = "list"
        it["score"] = 50 - (c.NOW - it["ts"]).total_seconds() / 3600 / 24 + 2 * it["outlets"]
        it["signal"] = f'Carried by {it["outlets"]} outlets' if it["outlets"] >= 3 else ""
    return sorted(out, key=lambda x: -x["score"])


# Radio show-prep humor (Boss 2026-10-19): funny things, sarcastic takes on viral stuff and culture, one line, no click.
DAY_FEEDS = [("Checkiday", "https://www.checkiday.com/rss.php"), ("National Day Calendar", "https://nationaldaycalendar.com/feed/")]
VIRAL_FEEDS = [("Daily Dot", "https://www.dailydot.com/feed/"), ("Know Your Meme", "https://knowyourmeme.com/newsfeed.rss")]
SATIRE_FEEDS = [("The Onion", "https://theonion.com/rss")]


SERIOUS_DAY = re.compile(r"awareness|prevention|disease|violence|cancer|memorial|remembrance|syndrome|disorder|"
                         r"infection|abuse|suicide|hunger|lgbt|diversity|pediatric|safety|saint|\bst\. |feast|"
                         r"independence|republic|liberation|national day of|martyr|genocide|holocaust|war\b", re.I)
WEEK_DAYS = 7  # Boss (2026-10-21): jocks voice track up to a week ahead, so Humor carries the next 7 days


def day_story(c, url, cache):
    """The 'story behind it' paragraphs from a Checkiday day page, cached by url."""
    if url in cache:
        return cache[url]
    try:
        h = c.get(url)
    except Exception:
        return ""
    ps = [c.text(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", h, re.S)]
    ps = [p for p in ps if len(p) > 80 and "Observed" not in p and "View All Events" not in p and "Subscribe" not in p]
    intro = re.search(r'<meta property="og:description" content="([^"]*)"', h)
    intro = c.text(intro.group(1)).rstrip("\u2026") if intro else ""
    if intro and re.search(r"is being observed|is observed next on", intro):  # Checkiday stock line, no write-up
        intro = ""
    cache[url] = " ".join([intro] + ps[:3]).strip()[:1200]
    return cache[url]


def week_days(c):
    """Fun national days for today and the next 6 days, from Checkiday's date pages, with the story behind each."""
    import datetime as dt
    from concurrent.futures import ThreadPoolExecutor
    start = c.NOW.astimezone(c.CT).date()
    found = []
    for n in range(WEEK_DAYS):
        d = start + dt.timedelta(days=n)
        try:
            h = c.get(f"https://www.checkiday.com/{d.month}/{d.day}/{d.year}")
        except Exception:
            c.FAILED.append(f"Checkiday {d}")
            continue
        seen = set()
        for url, name in re.findall(r'<h2 class="mdl-card__title-text"><a href="(https://www\.checkiday\.com/[0-9a-f]{32}/[^"]+)">(.*?)</a>', h):
            name = c.text(name)
            if url in seen or not re.search(r"\bDay\b", name) or SERIOUS_DAY.search(name) \
                    or c.TRAGIC.search(name) or c.POLITICS.search(name):
                continue
            seen.add(url)
            found.append({"col": "humor", "kind": "day", "title": name, "source": "Checkiday", "url": url,
                          "date": d.isoformat(), "ts": c.NOW, "gn": False, "outlets": 1, "also": [],
                          "score": 60 - n, "signal": "", "town": "", "tier": None, "scope": "", "desc": ""})
    path = c.DATA / "day_stories.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    with ThreadPoolExecutor(4) as pool:
        stories = list(pool.map(lambda it: day_story(c, it["url"], cache), found))
    for it, s in zip(found, stories):
        it["desc"] = s
    keep = {it["url"] for it in found}
    path.write_text(json.dumps({u: s for u, s in cache.items() if u in keep}, indent=0, ensure_ascii=False))
    return found


def show_prep(c):
    """Quirky national days for the coming week, viral culture stories and apolitical satire headlines.
    Claude writes the one-line funny take each morning; the feeds only supply the topic."""
    today = c.NOW.astimezone(c.CT)
    out = week_days(c)
    for label, url in DAY_FEEDS:
        for it in c.pull(("feed", "humor", label, url)):
            t = re.sub(r"\s*[-\u2013]\s*\w+ \d{1,2}, \d{4}$", "", it["title"]).strip()
            same_day = it["ts"].astimezone(c.CT).date() == today.date() or today.strftime("%B %-d, %Y") in it["title"]
            serious = re.search(r"awareness|prevention|disease|violence|cancer|memorial|remembrance|syndrome|"
                                r"disorder|infection|abuse|suicide|hunger|lgbt|diversity|pediatric|safety", t, re.I)
            if same_day and re.search(r"\bDay\b", t, re.I) and not serious and not (c.TRAGIC.search(t) or c.POLITICS.search(t)):
                out.append(dict(it, title=t.title() if t.isupper() else t, kind="day", score=60, signal="",
                                date=today.date().isoformat()))
    for label, url in VIRAL_FEEDS + SATIRE_FEEDS:
        for it in c.pull(("feed", "humor", label, url)):
            if (c.NOW - it["ts"]).total_seconds() > 48 * 3600:
                continue
            t = it["title"]
            if DIRTY.search(t) or c.TRAGIC.search(t) or c.POLITICS.search(t) or c.ICE.search(t) or c.GOSSIP.search(t):
                continue
            kind = "satire" if label in dict(SATIRE_FEEDS) else "viral"
            out.append(dict(it, kind=kind, score=50, signal="Satire" if kind == "satire" else "Trending online"))
    # one card per topic: national-day feeds overlap
    seen, uniq = set(), []
    for it in out:
        k = re.sub(r"[^a-z]", "", it["title"].lower())[:40]
        if k not in seen:
            seen.add(k)
            uniq.append(it)
    return uniq


def collect(c):
    """Show-prep humor plus one-line jokes. Boss (2026-10-19): no tweet or post roundups in Humor."""
    jokes, dropped = reddit_jokes(c)
    lists = show_prep(c)
    if dropped:
        print("humor dropped:", dropped)
    return jokes, lists


def record_shown(c, jokes):
    """Remember jokes that made the board so they never run twice."""
    path = c.DATA / "humor_shown.json"
    have = shown(c)
    texts = {r["text"] for r in have}
    today = c.NOW.astimezone(c.CT).date().isoformat()
    for j in jokes:
        t = f'{j["title"]} {j.get("punch", "")}'.strip()
        if t not in texts:
            have.append({"text": t, "day": today})
    path.write_text(json.dumps(have, indent=0, ensure_ascii=False))
