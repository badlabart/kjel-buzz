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
REDDIT = "https://www.reddit.com/r/dadjokes+cleanjokes+oneliners+Jokes/top/.rss?t=week&limit=100"
LIST_FEEDS = [
    ("HuffPost", "https://www.huffpost.com/section/comedy/feed"),
    ("Pleated Jeans", "https://pleated-jeans.com/feed/"),
    ("Cheezburger", "https://cheezburger.com/rss"),
]
LIST_Q = '"funniest tweets" OR "funniest posts" OR "funniest parenting" OR "hilarious tweets"'
MAX_JOKE_CHARS = 280  # fits a 15-25 second break
DIRTY = re.compile(
    r"\b(sex\w*|penis|vagina|dick|cock|boobs?|tits?|ass|asses|asshole|fuck\w*|shit\w*|bitch\w*|porn\w*|naked|nude|"
    r"horny|orgasm|condoms?|viagra|blow ?jobs?|whores?|sluts?|hookers?|strippers?|erection|testicl\w*|balls|"
    r"weed|stoned|cocaine|meth|hitler|nazis?|rape\w*|virgin\w*|wank\w*|masturbat\w*|panties|thong|nipples?|"
    r"genital\w*|pubes?|bang(ed|ing)?|screw(ed|ing)?|69|lesbian|gay|tranny|retard\w*|n-word|nsfw|cum|"
    r"autoerotic|asphyxia\w*|piss\w*|cheat\w*|affair|mistress|dildo|kinky|bdsm|hooters)\b", re.I)
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


def shown(c):
    path = c.DATA / "humor_shown.json"
    return json.loads(path.read_text()) if path.exists() else []


def reddit_jokes(c):
    try:
        root = ET.fromstring(c.get(REDDIT))
    except Exception as e:
        c.FAILED.append(f"Reddit jokes ({str(e)[:40]})")
        return [], {}
    old = [c.words(j) for j in classics(c)]
    seen = [c.words(j) for j in shown(c)]
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
                    "signal": f"#{rank} of this week's 100 top-voted Reddit jokes"})
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


def collect(c):
    jokes, dropped = reddit_jokes(c)
    lists = roundups(c)
    if dropped:
        print("humor dropped:", dropped)
    return jokes, lists


def record_shown(c, jokes):
    """Remember jokes that made the board so they never run twice."""
    path = c.DATA / "humor_shown.json"
    have = shown(c)
    for j in jokes:
        t = f'{j["title"]} {j.get("punch", "")}'.strip()
        if t not in have:
            have.append(t)
    path.write_text(json.dumps(have, indent=0, ensure_ascii=False))
