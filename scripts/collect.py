"""Collect buzz candidates for the KJEL Buzz Report -> data/pool.json, then print the shortlist.

Run: python3 -I scripts/collect.py
The shortlist is what Claude picks from. Nothing here writes the board; build.py does.
"""
import base64
import email.utils
import html
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import md5
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "url_cache.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
NOW = datetime.now(timezone.utc)
FRESH_HOURS = {"national": 48, "music": 48, "local": 24 * 7}
SHORT = {"national": 30, "music": 30, "local": 40}
PER_SOURCE = {"national": 3, "music": 4, "local": 6}  # cap per outlet in the shortlist
FAILED = []


def get(url, data=None, headers=None, timeout=25):
    h = {"User-Agent": UA}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def text(s):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def gn(q, days):
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(f"{q} when:{days}d")
            + "&hl=en-US&gl=US&ceid=US:en")


# ---------------- sources ----------------
SEASON = {
    1: '"snow day" OR "New Year" OR "ice fishing"', 2: '"Valentine\'s" OR "Super Bowl" OR "Groundhog"',
    3: '"St. Patrick\'s" OR "March Madness" OR "spring break"', 4: 'Easter OR prom OR "turkey season"',
    5: 'graduation OR "Mother\'s Day" OR "Memorial Day"', 6: '"Father\'s Day" OR "summer vacation" OR fishing',
    7: '"Fourth of July" OR fireworks OR "county fair"', 8: '"back to school" OR "state fair"',
    9: 'tailgate OR "homecoming" OR "pumpkin spice"', 10: 'Halloween OR pumpkin OR costume OR "corn maze"',
    11: 'Thanksgiving OR "deer season" OR "Black Friday"', 12: 'Christmas OR "Christmas lights" OR Santa',
}
NATIONAL_Q = [
    '"goes viral" OR "went viral" OR "viral video"',
    'heartwarming OR "feel-good" OR "pays it forward" OR "random act of kindness"',
    'weird OR bizarre OR "odd news" OR hilarious',
    '(dog OR cat OR puppy OR kitten OR horse OR goat OR cow) (rescued OR adorable OR viral OR reunited)',
    '"world record" OR "Guinness World Records"',
    '(lottery OR jackpot OR scratch-off) winner',
    '(Chiefs OR "St. Louis Cardinals" OR Mizzou OR "Kansas City Royals") (fans OR viral OR celebrate OR record)',
    SEASON[NOW.month],
]
NATIONAL_FEEDS = [
    ("UPI Odd News", "https://rss.upi.com/news/odd_news.rss"),
    ("Good News Network", "https://www.goodnewsnetwork.org/feed/"),
    ("Upworthy", "https://www.upworthy.com/feed"),
    ("Fox News Lifestyle", "https://moxie.foxnews.com/google-publisher/lifestyle.xml"),
]
LOCAL_Q = [
    '"Lebanon, Mo." OR "Lebanon, Missouri" OR "Lebanon, MO"',
    '"Laclede County"',
    'Lebanon Missouri "Route 66"',
    '"Lebanon R-3" OR "Lebanon Yellowjackets" OR "Bennett Spring"',
    'site:laclederecord.com',
    '"Lake of the Ozarks" OR "Osage Beach" OR Camdenton OR "Lake Ozark"',
    '"Camden County" Missouri',
    '"Pulaski County" Missouri OR "Fort Leonard Wood" OR Waynesville OR "St. Robert"',
    '"Webster County" Missouri OR "Marshfield, Mo." OR "Seymour, Mo."',
    '"Dallas County" Missouri OR "Buffalo, Mo."',
    '"Wright County" Missouri OR "Mountain Grove" OR "Hartville, Mo." OR "Mansfield, Mo."',
    '"Miller County" Missouri OR "Eldon, Mo." OR "Iberia, Mo."',
    'site:lakeexpo.com',
    'Ozarks (heartwarming OR viral OR "first ever" OR record OR rescued OR celebrates OR surprise)',
    '"Springfield, Mo." (heartwarming OR viral OR celebrates OR record OR "first ever" OR opens)',
    'Branson (new OR record OR viral OR celebrates OR opens)',
]
LOCAL_FEEDS = [
    ("My Ozarks Online", "https://www.myozarksonline.com/feed/"),
    ("City of Lebanon", "https://www.lebanonmissouri.org/RSSFeed.aspx?ModID=1&CID=All-newsflash.xml"),
    ("Downtown Lebanon", "https://www.downtownlebanonmo.com/feed/"),
    ("KY3", "https://www.ky3.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("OzarksFirst", "https://www.ozarksfirst.com/feed/"),
]
MUSIC_Q = ['"country music" OR "country singer" OR "country star"']
MUSIC_FEEDS = [
    ("Taste of Country", "https://tasteofcountry.com/feed/"),
    ("The Boot", "https://theboot.com/feed/"),
    ("Whiskey Riff", "https://www.whiskeyriff.com/feed/"),
    ("Saving Country Music", "https://www.savingcountrymusic.com/feed"),
    ("Billboard", "https://www.billboard.com/c/music/country/feed/"),
    ("Rolling Stone", "https://www.rollingstone.com/music/music-country/feed/"),
    ("Country Now", "https://countrynow.com/feed/"),
]

# Towns: tier 0 = Lebanon, 1 = the 7 counties + lake, 2 = wider Ozarks (filler only).
LEBANON = re.compile(r"\bLebanon\b|\bLaclede\b|Bennett Spring|Yellowjackets", re.I)
NOT_MO_LEBANON = re.compile(r"Lebanon,? (Ohio|OH|Pa\.?|Pennsylvania|Tenn\.?|Tennessee|TN|N\.?H\.?|New Hampshire|Ind\.?|Indiana|Ky\.?|Kentucky|Ore\.?|Oregon|Ill\.?|Illinois|Conn\.?|Va\.?|Virginia)|\bBeirut\b|\bLebanese\b|Israel|Hezbollah", re.I)
LEBANON_SOURCES = {"Laclede County Record", "My Ozarks Online", "City of Lebanon", "Downtown Lebanon"}
MO_MARK = re.compile(r"\b(Mo\.|MO|Missouri|Ozarks?)\b")
LOCAL_OUTLET = re.compile(
    r"laclede|ozark|ky3|kolr|kspr|lakeexpo|lake sun|lake news|news-leader|branson globe|reflex|webster county citizen|"
    r"marshfield mail|komu|krcg|kmzu|ksmu|krms|kttn|sgf|springfield daily|sedalia|daily guide|missouri|lebanon|"
    r"myozarks|guidon|houston herald|eldon", re.I)
COUNTY_TOWNS = [
    "Conway", "Phillipsburg", "Stoutland", "Eldridge", "Brumley",
    "Waynesville", "St. Robert", "Saint Robert", "Fort Leonard Wood", "Dixon", "Crocker", "Richland", "Laquey", "Pulaski County",
    "Camdenton", "Osage Beach", "Linn Creek", "Sunrise Beach", "Climax Springs", "Macks Creek", "Lake Ozark", "Lake of the Ozarks", "Camden County", "Laurie", "Gravois Mills",
    "Marshfield", "Seymour", "Rogersville", "Fordland", "Niangua", "Webster County",
    "Buffalo", "Louisburg", "Urbana", "Dallas County",
    "Mountain Grove", "Hartville", "Mansfield", "Norwood", "Wright County",
    "Eldon", "Tuscumbia", "Iberia", "Miller County",
]
WIDER_TOWNS = ["Springfield", "Branson", "Rolla", "Bolivar", "Nixa", "Ozark", "Republic", "West Plains", "Ozarks"]


def town_of(title, desc, source):
    blob = f"{title} {desc}"
    if not (source in LEBANON_SOURCES or LOCAL_OUTLET.search(source) or MO_MARK.search(blob)):
        return None, None
    if source in LEBANON_SOURCES and not NOT_MO_LEBANON.search(blob):
        m = re.search(r"\b(" + "|".join(map(re.escape, COUNTY_TOWNS)) + r")\b", title)
        if m and not LEBANON.search(title):
            return m.group(1), 1
        return "Lebanon", 0
    if LEBANON.search(blob) and not NOT_MO_LEBANON.search(blob):
        return "Lebanon", 0
    for t in COUNTY_TOWNS:
        if re.search(r"\b" + re.escape(t) + r"\b", blob, re.I):
            return t.replace("Saint Robert", "St. Robert").replace("Lake of the Ozarks", "Lake"), 1
    for t in WIDER_TOWNS:
        if re.search(r"\b" + re.escape(t) + r"\b", blob):
            return t, 2
    return None, None


# ---------------- filters ----------------
TRAGIC = re.compile(
    r"\b(murder\w*|homicide|kill(ed|s|ing)?|dead|dies|died|death|deaths|fatal\w*|shoot\w*|shot|stab\w*|gunman|"
    r"gunfire|arrest\w*|charged|charges|sentenc\w*|indict\w*|convicted|guilty|plead\w*|prison|jail\w*|inmate|"
    r"abus\w*|assault\w*|rape|molest\w*|overdose|drown\w*|suicide|missing|body found|remains|obituar\w*|funeral|"
    r"passed away|cancer|tragic|tragedy|grie(f|ving)|mourn\w*|victim\w*|suspect\w*|kidnap\w*|trafficking|crash\w*|"
    r"wreck|collision|injur\w*|airlift\w*|hospitali[sz]ed|critical condition|explosion|layoffs?|laid off|"
    r"bankrupt\w*|recall\w*|measles|outbreak|tornado|flood\w*|evacuat\w*|scam\w*|fraud|die|dying|arson\w*|"
    r"accused|fire|fires|blaze|burn(ed|s)? down|unsafe|destroyed)\b", re.I)
POLITICS = re.compile(
    r"\b(trump|biden|vance|harris|obama|democrat\w*|republican\w*|gop|congress\w*|senat\w*|legislat\w*|"
    r"lawmaker\w*|election\w*|ballot|voters?|voting|campaign\w*|candidate\w*|governor|kehoe|hawley|schmitt|"
    r"white house|administration|immigra\w*|deport\w*|tariff\w*|shutdown|supreme court|lawsuit|sue[sd]?|"
    r"court|judge|attorney general|protest\w*|israel|gaza|ukraine|russia|iran|press secretary|mamdani|noem|"
    r"kennedy center|amendment|proposition|ordinance|tax(es)?|council|commission\w*|data center|politic\w*|"
    r"midterms?)\b", re.I)
ICE = re.compile(r"\bICE\b")
GOSSIP = re.compile(
    r"\b(divorc\w*|split|splits|breakup|break up|cheat\w*|affair|feud\w*|slam\w*|blast\w*|rehab|dui|scandal|"
    r"spoiler\w*|backlash|controvers\w*|accus\w*|allegation\w*|threat\w*|harass\w*|meltdown|diss|outrage\w*)\b", re.I)
ENGLISH = re.compile(r"\b(the|a|an|to|of|in|and|for|is|on|with|at|from|his|her|after|this|how|why|what|new|gets|says)\b", re.I)
# Spam and non-US stories that ride Google News "viral" searches.
SPAM = re.compile(r"x{3}|xnxx|\bmms\b|\bleak(ed)?\b|uncut|[\U0001F300-\U0001FAFF]|\b(?=\w*\d)(?=\w*[a-z])(?=\w*[A-Z])\w{8,}\b", re.I)
FOREIGN = re.compile(
    r"\b(pakistan\w*|india\w*|bollywood|bigg boss|cricket|lakh|crore|rs\.? ?\d|premier league|nigeria\w*|"
    r"philippin\w*|kenya\w*|bangladesh\w*|duchess|royal family|prince \w+|king charles)\b", re.I)
JUNK = re.compile(
    r"(realtor\.com|zillow|apartments\.com|maxpreps|legacy\.com|holman-howe|funeral home|for sale|\bquiz\b|"
    r"live cams|products you|amazon|coupon|deals?\b|horoscope|crossword|wordle|connections hint|"
    r"winning numbers|lottery numbers|\bstocks?\b|nasdaq|s&p|dow jones|earnings|^opinion|announcements|"
    r"question of the week|e-edition|classifieds|public notice|trading post|archives|letters? to the editor|"
    r"^watch live|weather (alert|watch|warning)|forecast|results for|pick 3|cash pop|don't pay|full price|"
    r"tribute wall|schedule|^(monday|tuesday|wednesday|thursday|friday|saturday|sunday), \w+ \d|"
    r"maxpreps|sports illustrated|lyrics|sponsored)", re.I)
DOWNER = re.compile(
    r"\b(fire|fires|storm\w*|hospital|police|sheriff|deput\w*|warn\w*|closed|closing|closure|outage|unsafe|"
    r"delay\w*|shortage|debt|lawsuit|paychecks?|hot buses|concern\w*|worr\w*|danger\w*|risk)\b", re.I)
FUN = re.compile(
    r"\b(viral|hilarious|funny|adorable|heartwarming|wholesome|surpris\w*|record|first[- ]ever|rescued|reunit\w*|"
    r"celebrat\w*|wins?|winner|giant|biggest|pumpkin|halloween|costume|dog|puppy|cat|kitten|goat|horse|bear|"
    r"emu|fish\w*|trophy|champion\w*|propos\w*|wedding|birthday|anniversary|grand opening|opens|opening|"
    r"festival|parade|honou?rs?|award\w*|donat\w*|volunteer\w*|hero\w*|kindness|neon|route 66|duet|"
    r"no\. 1|number one|tour|new song|new album|surprise|sings?|cover)\b", re.I)


def blocked(col, title, desc, src=""):
    blob = f"{title} {desc[:200]}"
    if JUNK.search(f"{title} | {src}"):
        return "junk"
    if SPAM.search(title):
        return "spam"
    if col == "national" and FOREIGN.search(blob):
        return "non-US"
    if col == "national" and not ENGLISH.search(title):
        return "not English"
    if TRAGIC.search(title) or POLITICS.search(title) or ICE.search(title):
        return "downer/politics"
    if col != "local" and GOSSIP.search(title):
        return "gossip"
    if col == "local" and re.fullmatch(r"[A-Z][\w.\"'()\- ]{2,40}", title) and len(title.split()) <= 4:
        return "obit-style title"
    if TRAGIC.search(blob) and col == "local":
        return "downer in summary"
    return None


# ---------------- parsing ----------------
def parse_feed(body, source, col, from_gn=False, days=None):
    body = body.lstrip()
    root = ET.fromstring(body)
    out = []
    for it in root.findall(".//item"):
        title = text((it.findtext("title") or ""))
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
        try:
            ts = email.utils.parsedate_to_datetime(pub)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            try:
                ts = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                continue
        src = source
        desc = text(it.findtext("description") or "")
        if from_gn:
            s = it.find("source")
            src = (s.text or "").strip() if s is not None else "Google News"
            if title.endswith(" - " + src):
                title = title[: -len(src) - 3].strip()
            desc = ""  # Google News descriptions only repeat the headline
        out.append({"col": col, "title": title, "url": link, "source": src, "ts": ts, "desc": desc[:400],
                    "gn": from_gn, "query": days})
    return out


def pull(job):
    kind, col, label, url = job
    try:
        body = get(url)
        return parse_feed(body, label, col, from_gn=(kind == "gn"))
    except Exception as e:
        FAILED.append(f"{label} ({str(e)[:40]})")
        return []


def google_trends():
    """Top US searches today with their news stories. Returns story items with a search-count signal."""
    ns = {"ht": "https://trends.google.com/trending/rss"}
    out = []
    try:
        root = ET.fromstring(get("https://trends.google.com/trending/rss?geo=US"))
    except Exception as e:
        FAILED.append(f"Google Trends ({str(e)[:40]})")
        return out
    for it in root.findall(".//item"):
        traffic = it.findtext("ht:approx_traffic", "", ns)
        for n in it.findall("ht:news_item", ns)[:1]:
            out.append({"col": "national", "title": text(n.findtext("ht:news_item_title", "", ns)),
                        "url": n.findtext("ht:news_item_url", "", ns), "source": n.findtext("ht:news_item_source", "", ns),
                        "ts": NOW, "desc": "", "gn": False, "trend": traffic, "trend_term": it.findtext("title")})
    return out


def wikipedia_top():
    """Article -> views for yesterday's most-read English Wikipedia pages."""
    y = NOW - timedelta(days=1)
    try:
        d = json.loads(get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{y:%Y/%m/%d}"))
    except Exception as e:
        FAILED.append(f"Wikipedia ({str(e)[:40]})")
        return {}
    top = {}
    for a in d["items"][0]["articles"][:150]:
        name = re.sub(r"\s*\(.*\)$", "", a["article"].replace("_", " "))
        if ":" in name or name == "Main Page" or len(name) < 8 or " " not in name:
            continue
        top.setdefault(name, a["views"])
    return top


def billboard_artists():
    """Artist -> best rank on Billboard Hot Country Songs."""
    try:
        b = get("https://www.billboard.com/charts/country-songs/", timeout=40)
    except Exception as e:
        FAILED.append(f"Billboard chart ({str(e)[:40]})")
        return {}
    out = {}
    for rank, row in enumerate(b.split('class="o-chart-results-list-row-container"')[1:51], 1):
        a = re.search(r'id="title-of-a-story".*?</h3>\s*<span[^>]*>(.*?)</span>', row, re.S)
        if not a:
            continue
        for name in re.split(r"\s+(?:Featuring|&|And|With|x|X)\s+|,\s*", text(a.group(1))):
            name = name.strip()
            if len(name) > 3 and name not in out:
                out[name] = rank
    return out


# ---------------- clustering + scoring ----------------
STOP = set("a an the of to in on at for and or with by from is are was were be as it its this that after new over "
           "into up out about his her their your you we our mo missouri".split())


def words(t):
    return {w for w in re.findall(r"[a-z0-9']+", t.lower()) if w not in STOP and len(w) > 2}


def cluster(items):
    """Group near-identical headlines from different outlets. Keeps the best-sourced item per group."""
    groups = []
    for it in sorted(items, key=lambda x: x["ts"], reverse=True):
        w = words(it["title"])
        for g in groups:
            if g["col"] == it["col"] and w and len(w & g["w"]) / max(1, len(w | g["w"])) >= 0.55:
                g["sources"].add(it["source"])
                g["members"].append(it)
                break
        else:
            groups.append({"col": it["col"], "w": w, "sources": {it["source"]}, "members": [it]})
    out = []
    for g in groups:
        best = sorted(g["members"], key=lambda x: (x["gn"], x.get("trend") is None, -x["ts"].timestamp()))[0]
        best = dict(best)
        best["outlets"] = len(g["sources"])
        best["also"] = sorted(g["sources"] - {best["source"]})[:4]
        best["trend"] = next((m["trend"] for m in g["members"] if m.get("trend")), None)
        best["ts"] = max(m["ts"] for m in g["members"]) if best["gn"] else best["ts"]
        out.append(best)
    return out


def traffic_num(s):
    m = re.match(r"([\d,]+)", s or "")
    return int(m.group(1).replace(",", "")) if m else 0


def short_num(n):
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n // 1000}K" if n >= 1000 else str(n)


def score(it, wiki, chart):
    hours = max(0.0, (NOW - it["ts"]).total_seconds() / 3600)
    blob = f'{it["title"]} {it["desc"][:200]}'
    s = 10 + 4 * math.log2(max(1, it["outlets"]))
    signals = []
    if it.get("trend"):
        s += 3 * math.log10(max(10, traffic_num(it["trend"])))
        signals.append(f'Google searches today: {it["trend"]}')
    if it["outlets"] >= 3:
        signals.append(f'Carried by {it["outlets"]} outlets')
    for name, views in wiki.items():
        if name.lower() in blob.lower():
            s += 4
            signals.append(f"Wikipedia: {short_num(views)} reads yesterday ({name})")
            break
    if it["col"] == "music":
        hits = [(r, a) for a, r in chart.items() if re.search(r"\b" + re.escape(a) + r"\b", it["title"])]
        if hits:
            r, a = min(hits)
            s += 6 + (50 - r) / 10
            signals.append(f"{a}: #{r} on Billboard Hot Country")
    s += min(9, 3 * len(set(m.group(0).lower() for m in FUN.finditer(blob))))
    s -= 6 * len(set(m.group(0).lower() for m in DOWNER.finditer(it["title"])))
    if it["source"] in ("UPI Odd News", "Good News Network", "Upworthy"):
        s += 2
    if it["col"] == "local":
        s += {0: 8, 1: 4, 2: 0}[it["tier"]]
        s -= hours / 24 * 2
    else:
        s -= hours / 6
    it["score"] = round(s, 1)
    it["signal"] = " · ".join(signals[:2])


# ---------------- link resolving ----------------
def resolve_gn(link, cache):
    if link in cache:
        return cache[link]
    gid = link.split("/articles/")[1].split("?")[0]
    url = None
    try:
        raw = base64.urlsafe_b64decode(gid + "=" * (-len(gid) % 4))
        m = re.search(rb"https?://[\x21-\x7e]+", raw)
        if m and not gid.startswith("AU_yqL"):
            url = m.group(0).decode()
    except Exception:
        pass
    if not url:
        page = get(f"https://news.google.com/articles/{gid}?hl=en-US&gl=US&ceid=US:en")
        sg = re.search(r'data-n-a-sg="([^"]+)"', page)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page)
        if sg and ts:
            inner = json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None,
                                                None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                                gid, int(ts.group(1)), sg.group(1)])
            body = "f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", inner, None, "generic"]]]))
            r = get("https://news.google.com/_/DotsSplashUi/data/batchexecute", body.encode(),
                    {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
            m = re.search(r'garturlres\\",\\"(https?:[^"\\]+)', r)
            url = m.group(1) if m else None
    if url:
        cache[link] = url
    return url


def page_summary(url):
    try:
        h = get(url, timeout=15)[:300000]
    except Exception:
        return ""
    for pat in (r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"',
                r'<meta[^>]+content="([^"]*)"[^>]+property="og:description"',
                r'<meta[^>]+name="description"[^>]+content="([^"]*)"'):
        m = re.search(pat, h, re.I)
        if m and len(text(m.group(1))) > 30:
            return text(m.group(1))[:400]
    return ""


def resolve_all(items, limit=None):
    """Swap Google News links for publisher links. Google throttles this, so: one at a time, cached,
    and stop at the first 429. Unresolved items keep the Google News link, which still opens the story."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    tried = 0
    for it in items:
        if not it.get("gn_url") and it["url"].startswith("https://news.google.com"):
            it["gn_url"] = it["url"]
        if not it["url"].startswith("https://news.google.com"):
            continue
        if it["url"] not in cache and limit is not None and tried >= limit:
            continue
        try:
            tried += it["url"] not in cache
            real = resolve_gn(it["url"], cache)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                FAILED.append("Google News link lookup (429, rest keep Google links)")
                break
            real = None
        except Exception:
            real = None
        if real:
            it["url"] = real
        time.sleep(1.2)
    CACHE.write_text(json.dumps(cache, indent=0))


def summaries(items):
    todo = [i for i in items if not i["desc"] and not i["url"].startswith("https://news.google.com")]
    with ThreadPoolExecutor(6) as ex:
        for it, d in zip(todo, ex.map(lambda i: page_summary(i["url"]), todo)):
            it["desc"] = d


# ---------------- main ----------------
def main():
    DATA.mkdir(exist_ok=True)
    jobs =[("gn", "national", "Google News", gn(q, 1)) for q in NATIONAL_Q]
    jobs += [("feed", "national", l, u) for l, u in NATIONAL_FEEDS]
    jobs += [("gn", "local", "Google News", gn(q, 7)) for q in LOCAL_Q]
    jobs += [("feed", "local", l, u) for l, u in LOCAL_FEEDS]
    jobs += [("gn", "music", "Google News", gn(q, 1)) for q in MUSIC_Q]
    jobs += [("feed", "music", l, u) for l, u in MUSIC_FEEDS]
    with ThreadPoolExecutor(6) as ex:
        raw = [it for chunk in ex.map(pull, jobs) for it in chunk]
    raw += google_trends()
    wiki, chart = wikipedia_top(), billboard_artists()

    kept, dropped = [], {}
    for it in raw:
        age_h = (NOW - it["ts"]).total_seconds() / 3600
        if age_h > FRESH_HOURS[it["col"]] or not it["title"]:
            continue
        why = blocked(it["col"], it["title"], it["desc"], it["source"])
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        if it["col"] == "local":
            it["town"], it["tier"] = town_of(it["title"], it["desc"], it["source"])
            if it["town"] is None:
                dropped["outside area"] = dropped.get("outside area", 0) + 1
                continue
        kept.append(it)

    items = cluster(kept)
    for it in items:
        it["id"] = it["col"][0].upper() + md5((it["title"] + it["source"]).encode()).hexdigest()[:6]
        score(it, wiki, chart)

    direct = {l for l, _ in NATIONAL_FEEDS + LOCAL_FEEDS + MUSIC_FEEDS}
    short = []
    for col in ("national", "local", "music"):
        rows = sorted((i for i in items if i["col"] == col), key=lambda x: -x["score"])
        pick, per_src = [], {}
        for i in rows:  # top 3 from each direct feed first, so one hot query can't crowd them out
            if i["source"] in direct and per_src.get(i["source"], 0) < min(3, PER_SOURCE[col]):
                pick.append(i)
                per_src[i["source"]] = per_src.get(i["source"], 0) + 1
        for i in rows:
            if len(pick) >= SHORT[col]:
                break
            if i not in pick and per_src.get(i["source"], 0) < PER_SOURCE[col]:
                pick.append(i)
                per_src[i["source"]] = per_src.get(i["source"], 0) + 1
        if col == "local":  # every Lebanon item that survived the filters goes to Claude
            pick += [i for i in rows if i["tier"] == 0 and i not in pick]
        short += pick
    for it in short:
        it["gn_url"] = it["url"] if it["gn"] else None
    top_gn = [i for col in ("national", "local", "music")
              for i in sorted((x for x in short if x["col"] == col and x["gn"]), key=lambda x: -x["score"])[:12]]
    resolve_all(top_gn)
    summaries(short)
    # Second pass: a resolved summary can reveal a downer the headline hid.
    short = [i for i in short if not (TRAGIC.search(i["desc"][:200]) or POLITICS.search(i["desc"][:200]))]

    pool = []
    for i in short:
        pool.append({k: i.get(k) for k in ("id", "col", "title", "source", "url", "gn_url", "desc", "outlets", "also",
                                           "signal", "score", "town", "tier")} | {"ts": i["ts"].isoformat()})
    (DATA / "pool.json").write_text(json.dumps({"collected": NOW.isoformat(), "items": pool}, indent=1, ensure_ascii=False))

    print(f"raw {len(raw)} | kept {len(kept)} | stories {len(items)} | shortlist {len(pool)} | dropped {dropped}")
    print("FAILED: " + (", ".join(FAILED) if FAILED else "none"))
    for col in ("national", "local", "music"):
        print(f"\n=== {col.upper()}")
        for i in sorted((p for p in pool if p["col"] == col), key=lambda x: -x["score"]):
            age = (NOW - datetime.fromisoformat(i["ts"])).total_seconds() / 3600
            age = f"{age:.0f}h" if age < 48 else f"{age / 24:.0f}d"
            where = f' [{i["town"]}{"*" if i["tier"] == 0 else ""}]' if col == "local" else ""
            print(f'{i["id"]} | {age} | {i["source"][:22]}{where} | {i["signal"] or "-"} | {i["title"]} || {i["desc"][:220]}')


if __name__ == "__main__":
    main()
