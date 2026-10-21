"""Candidates for Show Prep's TIMELY and THE JOHNSONS columns (Boss 2026-10-21).

TIMELY = things to talk about on the date they are for: radio-prep daily sheet (IanGardner.com), NWS forecast,
AAA gas prices, MDC season dates, and calendar countdowns. THE JOHNSONS = family, outdoors and life content
for Chris (37) and Jess (32): kid-safety recalls, parenting and cooking, Ozarks hunting and fishing, money and time.

Writes data/extra_pool.json and prints the shortlist. Separate from collect.py so a failure here never blocks the Buzz.
Run: python3 -I scripts/extra.py
"""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import md5
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
import collect  # noqa: E402  (reuses text(), words(), the downer/gossip filters)

CT = ZoneInfo("America/Chicago")
NOW = datetime.now(timezone.utc)
TODAY = datetime.now(CT).date()
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
NWS_UA = "KJEL-showprep (badlabart on GitHub)"
LEBANON = "37.6806,-92.6638"
FAILED = []


def get(url, ua=UA, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def uid(prefix, *parts):
    return prefix + md5("|".join(parts).encode()).hexdigest()[:6]


def day_name(d):
    return d.strftime("%A")


def ordinal_date(d):
    return d.strftime("%B ") + str(d.day)


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def in_days(d):
    n = (d - TODAY).days
    return "today" if n == 0 else "tomorrow" if n == 1 else f"in {n} days"


# ======================= TIMELY =======================
def ian_gardner(days=5):
    """IanGardner.com daily broadcast prep sheet (free, no sign-up). One dated page per day; future days appear as published."""
    out, seen_movies = [], set()
    for i in range(days):
        d = TODAY + timedelta(days=i)
        url = f"https://iangardner.com/daily-broadcast-prep-{d.isoformat()}"
        try:
            page = get(url)
        except Exception as e:
            if i == 0:
                FAILED.append(f"IanGardner prep ({str(e)[:40]})")
            break  # later days are not published yet
        for sec in page.split('<div class="prep-section">')[1:]:
            h2 = re.search(r"<h2>(.*?)</h2>", sec, re.S)
            name = collect.text(h2.group(1)) if h2 else ""
            if name not in ("National Day", "On This Day", "Movies & TV", "Birthdays"):
                continue
            for it in re.findall(r'<div class="prep-item">(.*?)</div>\s*(?=<div class="prep-item">|</div>|\s*$)', sec, re.S):
                strong = re.search(r"<strong>(.*?)</strong>", it, re.S)
                title = collect.text(strong.group(1)) if strong else ""
                body = re.sub(r"\s*Refresh for another .*? item\s*$", "", collect.text(re.sub(r"<strong>.*?</strong>", "", it, flags=re.S)))
                if not title and not body:
                    continue
                if name == "National Day" and re.search(r"\((UK|Canada|India|Australia|International)\)", title):
                    continue
                if name == "Movies & TV":
                    if not re.search(r"Cinema|Streaming|TV \(USA\)", title) or title in seen_movies:
                        continue
                    seen_movies.add(title)
                out.append({"id": uid("T", d.isoformat(), name, title, body[:40]), "kind": "timely", "section": name,
                            "date": d.isoformat(), "title": title, "desc": body[:420], "source": "IanGardner Daily Prep",
                            "url": url, "auto": False})
    return out


def weather():
    """NWS Springfield point forecast for Lebanon. Today and tomorrow always; later days only when something is worth saying."""
    out = []
    try:
        pt = json.loads(get(f"https://api.weather.gov/points/{LEBANON}", NWS_UA))["properties"]
        fc = json.loads(get(pt["forecast"], NWS_UA))["properties"]["periods"]
        alerts = json.loads(get(f"https://api.weather.gov/alerts/active?point={LEBANON}", NWS_UA))["features"]
    except Exception as e:
        FAILED.append(f"NWS forecast ({str(e)[:40]})")
        return out
    url = "https://forecast.weather.gov/MapClick.php?lat=37.6806&lon=-92.6638"
    for a in alerts:
        p = a["properties"]
        out.append({"id": uid("T", "alert", p["id"]), "kind": "timely", "section": "Weather", "label": "Weather Alert",
                    "date": TODAY.isoformat(), "line": f"The National Weather Service has a {p['event']} out for the Lebanon area: {collect.text(p.get('headline') or '')}.",
                    "source": "National Weather Service", "url": url, "auto": True})
    days = {}
    for p in fc:
        d = datetime.fromisoformat(p["startTime"]).date()
        days.setdefault(d, {})["day" if p["isDaytime"] else "night"] = p
    for d in sorted(days)[:5]:
        day, night = days[d].get("day"), days[d].get("night")
        if not day:  # tonight's period only
            continue
        hi, lo = day["temperature"], night["temperature"] if night else None
        pop = max((x["probabilityOfPrecipitation"]["value"] or 0) for x in (day, night) if x)
        wind = max(int(m) for m in re.findall(r"(\d+) mph", " ".join(x["windSpeed"] for x in (day, night) if x)) or [0])
        notable = pop >= 40 or (lo is not None and lo <= 38) or hi >= 85 or hi <= 45 or wind >= 20
        if d > TODAY + timedelta(days=1) and not notable:
            continue
        when = "Today" if d == TODAY else "Tomorrow" if d == TODAY + timedelta(days=1) else day_name(d)
        bits = [f"{day['shortForecast'].lower()}, a high near {hi}"]
        if lo is not None:
            bits.append(f"a low around {lo}")
        if pop >= 30:
            bits.append(f"a {pop} percent chance of rain")
        if wind >= 15:
            bits.append(f"wind up to {wind} miles an hour")
        line = f"{when}'s Lebanon forecast: " + ", ".join(bits[:1]) + "".join(f", {b}" for b in bits[1:]) + "."
        out.append({"id": uid("T", "wx", d.isoformat()), "kind": "timely", "section": "Weather", "label": "Weather",
                    "date": d.isoformat(), "line": line[0].upper() + line[1:], "source": "National Weather Service",
                    "url": url, "auto": True})
    return out


def gas():
    """AAA Missouri averages for regular unleaded, with the Springfield metro."""
    try:
        h = collect.text(get("https://gasprices.aaa.com/?state=MO"))
    except Exception as e:
        FAILED.append(f"AAA gas ({str(e)[:40]})")
        return []
    m = re.search(r"Missouri average gas prices Regular Mid-Grade Premium Diesel Current Avg\. \$(\d\.\d+) \$\d\.\d+ \$\d\.\d+ \$\d\.\d+ "
                  r"Yesterday Avg\. \$\d\.\d+ .*? Week Ago Avg\. \$(\d\.\d+) .*? Month Ago Avg\. \$(\d\.\d+) .*? Year Ago Avg\. \$(\d\.\d+)", h)
    if not m:
        FAILED.append("AAA gas (page changed)")
        return []
    now, wk, mo, yr = (float(x) for x in m.groups())
    sp = re.search(r"Springfield Regular Mid Premium Diesel Current Avg\. \$(\d\.\d+)", h)

    def move(a, b):
        c = round(abs(a - b) * 100)
        return "unchanged" if c == 0 else f"{'down' if a < b else 'up'} {plural(c, 'cent')}"
    line = (f"Missouri's average for regular gas is ${now:.2f} today, {move(now, mo)} from a month ago"
            f" and {'up' if now > yr else 'down'} ${abs(now - yr):.2f} from a year ago, according to AAA.")
    if sp:
        line += f" Springfield averages ${float(sp.group(1)):.2f}."
    return [{"id": uid("T", "gas", TODAY.isoformat()), "kind": "timely", "section": "Gas", "label": "Gas Prices",
             "date": TODAY.isoformat(), "line": line, "source": "AAA", "url": "https://gasprices.aaa.com/?state=MO", "auto": True}]


MDC_SEASONS = [("deer-archery", "Archery deer season"), ("deer-firearms-november-portion", "The November portion of firearms deer season"),
               ("deer-firearms-youth-portions", "Youth firearms deer season"), ("turkey-fall-firearms", "Fall firearms turkey season"),
               ("dove-hunting", "Dove season"), ("quail-hunting", "Quail season"), ("pheasant-hunting", "Pheasant season")]


def seasons():
    """MDC season pages: say it when a season opens or closes within 35 days, or is open for the whole next stretch."""
    out = []
    for slug, name in MDC_SEASONS:
        url = f"https://mdc.mo.gov/hunting-trapping/seasons/{slug}"
        try:
            t = collect.text(get(url))
        except Exception as e:
            FAILED.append(f"MDC {slug} ({str(e)[:30]})")
            continue
        sect = t[t.find("Season"):t.find("Hours")] if "Hours" in t else t[:600]
        ranges = [(datetime.strptime(a, "%B %d, %Y").date(), datetime.strptime(b, "%B %d, %Y").date())
                  for a, b in re.findall(r"([A-Z][a-z]+ \d{1,2}, \d{4}) - ([A-Z][a-z]+ \d{1,2}, \d{4})", sect)]
        for a, b in ranges:
            if TODAY < a <= TODAY + timedelta(days=35):
                line = (f"{name} opens {day_name(a)}, {ordinal_date(a)}, {in_days(a)}, and runs through {ordinal_date(b)}.")
            elif a <= TODAY <= b and TODAY <= b <= TODAY + timedelta(days=35):
                line = f"{name} ends {day_name(b)}, {ordinal_date(b)}, {in_days(b)}."
            else:
                continue
            out.append({"id": uid("T", "mdc", slug, a.isoformat()), "kind": "timely", "section": "Season", "label": "Hunting Season",
                        "date": TODAY.isoformat(), "line": line, "source": "Missouri Department of Conservation", "url": url, "auto": True})
    return out


def nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))
    return d


def countdowns():
    """Rule-based dates, computed so they can never be stale. No politics (Election Day is left out on purpose)."""
    y = TODAY.year
    fall_back = nth_weekday(y, 11, 6, 1)  # US rule: first Sunday of November
    items = [("Halloween", date(y, 10, 31), "Halloween is {wd}, {dt}, {when}."),
             ("Clocks Fall Back", fall_back, "Daylight saving time ends {wd}, {dt}, {when}, so clocks fall back one hour and sunset comes an hour earlier."),
             ("Veterans Day", date(y, 11, 11), "Veterans Day is {wd}, {dt}, {when}."),
             ("Thanksgiving", nth_weekday(y, 11, 3, 4), "Thanksgiving is {wd}, {dt}, {when}."),
             ("Black Friday", nth_weekday(y, 11, 3, 4) + timedelta(days=1), "Black Friday is {wd}, {dt}, {when}.")]
    out = []
    for label, d, tpl in items:
        if 0 <= (d - TODAY).days <= 35:
            out.append({"id": uid("T", "count", label, d.isoformat()), "kind": "timely", "section": "Season", "label": label,
                        "date": TODAY.isoformat(), "line": tpl.format(wd=day_name(d), dt=ordinal_date(d), when=in_days(d)),
                        "source": "Calendar", "url": "https://www.timeanddate.com/holidays/us/", "auto": True})
    return out


# ======================= THE JOHNSONS =======================
# (pillar, source label, feed url, max age in days). Pillar becomes the card's label.
FEEDS = [
    ("Family", "CPSC Recalls", "https://www.cpsc.gov/Newsroom/CPSC-RSS-Feed/Recalls-RSS", 14),
    ("Family", "Today's Parent", "https://www.todaysparent.com/feed/", 10),
    ("Family", "Scary Mommy", "https://www.scarymommy.com/feed", 7),
    ("Family", "Fatherly", "https://www.fatherly.com/feed", 21),
    ("Cooking", "Budget Bytes", "https://www.budgetbytes.com/feed/", 14),
    ("Cooking", "Skinnytaste", "https://www.skinnytaste.com/feed/", 14),
    ("Cooking", "The Kitchn", "https://www.thekitchn.com/main.rss", 7),
    ("Outdoors", "Outdoor Life", "https://www.outdoorlife.com/feed/", 7),
    ("Outdoors", "Field & Stream", "https://www.fieldandstream.com/feed/", 10),
    ("Outdoors", "MeatEater", "https://www.themeateater.com/feed", 10),
    ("Outdoors", "Wired2Fish", "https://www.wired2fish.com/feed", 10),
    ("Life", "Money Talks News", "https://www.moneytalksnews.com/feed/", 7),
    ("Life", "NerdWallet", "https://www.nerdwallet.com/blog/feed/", 7),
    ("Life", "Lifehacker", "https://lifehacker.com/feed/rss", 7),
]
KID = re.compile(r"\b(child|children|kid|kids|baby|babies|infant|toddler|crib|stroller|car seat|high ?chair|toys?|bassinet|youth|"
                 r"pajamas?|sleepwear|playpen|bunk bed|teether|pacifier|backpack|halloween|costume)\b", re.I)
# Things the Johnsons turn off (their outline): politics and polarizing topics, plus ads and shopping lists.
OFFTOPIC = re.compile(r"\b(trump|biden|harris|democrat\w*|republican\w*|gop|congress|senate|election|ballot|immigra\w*|abortion|"
                      r"gun control|transgender|woke|israel|gaza|ukraine|best deals?|prime day|black friday deals?|coupon code|sale alert|"
                      r"sponsored|giveaway|horoscope|zodiac|celebrity|kardashian|dating|sex|porn|cannabis|marijuana|weed)\b", re.I)
NICHE = re.compile(r"\b(ozarks|missouri|bennett spring|lake of the ozarks)\b", re.I)


def parse(body, pillar, source, max_days):
    root = ET.fromstring(body)
    out = []
    for it in root.findall(".//item"):
        title = collect.text(it.findtext("title") or "")
        link = (it.findtext("link") or "").strip()
        desc = collect.text(it.findtext("description") or "")[:600]
        raw_date = (it.findtext("pubDate") or "").strip()
        try:
            ts = parsedate_to_datetime(raw_date)
        except Exception:
            try:
                ts = datetime.strptime(raw_date, "%B %d, %Y")  # CPSC: "October 15, 2026"
            except ValueError:
                continue
        ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        if (NOW - ts).total_seconds() > max_days * 86400 or not title or not link:
            continue
        out.append({"title": title, "url": link, "desc": desc, "ts": ts, "pillar": pillar, "source": source})
    return out


def mdc_news():
    """Missouri Department of Conservation newsroom (no feed; read the list page)."""
    try:
        h = get("https://mdc.mo.gov/newsroom")
    except Exception as e:
        FAILED.append(f"MDC newsroom ({str(e)[:40]})")
        return []
    out = []
    for blk in h.split('<article about="/newsroom/')[1:]:
        slug = blk.split('"')[0]
        t = collect.text(blk[:6000])
        m = re.search(r"Media (.+?) by .+? ([A-Z][a-z]{2} \d{1,2}, \d{4}) Body (.*)", t)
        if not m:
            continue
        ts = datetime.strptime(m.group(2), "%b %d, %Y").replace(tzinfo=CT).astimezone(timezone.utc)
        if (NOW - ts).days > 10:
            continue
        out.append({"title": m.group(1).strip(), "url": "https://mdc.mo.gov/newsroom/" + slug, "desc": m.group(3)[:400], "ts": ts,
                    "pillar": "Outdoors", "source": "Missouri Dept. of Conservation"})
    return out


def reddit():
    """One combined pull, this week's top posts, ranked by votes. Reddit throttles repeat pulls, so a 429 is just skipped."""
    subs = "Frugal+personalfinance+productivity+simpleliving+Parenting+daddit+Mommit+hunting+Fishing+Missouri+EatCheapAndHealthy+MealPrepSunday"
    try:
        root = ET.fromstring(get(f"https://www.reddit.com/r/{subs}/top/.rss?t=week&limit=60"))
    except Exception as e:
        FAILED.append(f"Reddit ({str(e)[:40]})")
        return []
    A = "{http://www.w3.org/2005/Atom}"
    pillar = {"Frugal": "Life", "personalfinance": "Life", "productivity": "Life", "simpleliving": "Life", "Parenting": "Family",
              "daddit": "Family", "Mommit": "Family", "hunting": "Outdoors", "Fishing": "Outdoors", "Missouri": "Outdoors",
              "EatCheapAndHealthy": "Cooking", "MealPrepSunday": "Cooking"}
    out = []
    for rank, en in enumerate(root.findall(A + "entry"), 1):
        cat = en.find(A + "category")
        sub = cat.get("term") if cat is not None else ""
        md = re.search(r'<div class="md">(.*?)</div>', html.unescape(en.findtext(A + "content") or ""), re.S)
        body = collect.text(md.group(1)) if md else ""
        title = collect.text(en.findtext(A + "title") or "")
        link = en.find(A + "link")
        try:
            ts = datetime.fromisoformat(en.findtext(A + "updated"))
        except Exception:
            continue
        if sub not in pillar or len(body) < 120 or body in ("[removed]", "[deleted]"):
            continue  # picture and link posts carry no text to read from
        out.append({"title": title, "url": link.get("href") if link is not None else "", "desc": body[:600], "ts": ts,
                    "pillar": pillar[sub], "source": "r/" + sub, "signal": f"#{rank} this week on r/{sub}"})
    return out


def shown():
    p = DATA / "extra_shown.json"
    return json.loads(p.read_text()) if p.exists() else {}


def johnsons():
    jobs = []
    for pillar, label, url, days in FEEDS:
        try:
            jobs.append(parse(get(url), pillar, label, days))
        except Exception as e:
            FAILED.append(f"{label} ({str(e)[:40]})")
    items = [it for chunk in jobs for it in chunk] + mdc_news() + reddit()
    # Recently talked about everywhere: skip anything that matches a National or trending story already on the board.
    busy = []
    try:
        pool = json.loads((DATA / "pool.json").read_text())["items"]
        busy = [collect.words(i["title"]) for i in pool if i["col"] in ("national", "weird") or i.get("trend")]
    except Exception:
        pass
    seen = shown()
    out = []
    for it in items:
        blob = f'{it["title"]} {it["desc"][:200]}'
        if OFFTOPIC.search(blob) or collect.JUNK.search(it["title"]) or collect.SPAM.search(it["title"]):
            continue
        if it["source"] == "CPSC Recalls" and not KID.search(blob):
            continue
        w = collect.words(it["title"])
        if any(len(w & b) / max(1, len(w | b)) >= 0.5 for b in busy):
            continue
        it["id"] = uid("J", it["title"], it["source"])
        if it["id"] in seen:
            continue
        it["niche"] = bool(NICHE.search(blob)) or it["source"] in ("Missouri Dept. of Conservation", "CPSC Recalls")
        out.append(it)
    # Ozarks items first, then newest. At most 3 per source, sources interleaved so no one site fills a pillar.
    out.sort(key=lambda i: (not i["niche"], -i["ts"].timestamp()))
    per, rank = {}, {}
    for i in out:
        per[i["source"]] = per.get(i["source"], 0) + 1
        rank[i["id"]] = per[i["source"]]
    out = [i for i in out if rank[i["id"]] <= 3]
    out.sort(key=lambda i: (rank[i["id"]], not i["niche"], -i["ts"].timestamp()))
    return out


def main():
    DATA.mkdir(exist_ok=True)
    timely = ian_gardner() + weather() + gas() + seasons() + countdowns()
    jj = johnsons()
    cap = {"Family": 12, "Cooking": 6, "Outdoors": 14, "Life": 12}
    taken = {k: 0 for k in cap}
    jj = [i for i in jj if (taken.__setitem__(i["pillar"], taken[i["pillar"]] + 1) or taken[i["pillar"]] <= cap[i["pillar"]])]
    for i in jj:
        i["ts"] = i["ts"].isoformat()
    (DATA / "extra_pool.json").write_text(json.dumps({"made": TODAY.isoformat(), "timely": timely, "johnsons": jj}, indent=1, ensure_ascii=False))

    print(f"TIMELY: {len(timely)} items | THE JOHNSONS: {len(jj)} items | FAILED: {', '.join(FAILED) or 'none'}")
    print("\n== TIMELY (auto = line is written; keep it as is or improve it. Others need a line from you) ==")
    for t in timely:
        if t["auto"]:
            print(f'{t["id"]} | {t["date"]} | AUTO [{t["label"]}] {t["line"]}')
        else:
            print(f'{t["id"]} | {t["date"]} | {t["section"]} | {t["title"]} || {t["desc"][:300]}')
    print("\n== THE JOHNSONS (pillar | age | source | signal | headline || summary) ==")
    for i in jj:
        age = (NOW - datetime.fromisoformat(i["ts"])).total_seconds() / 3600
        print(f'{i["id"]} | {i["pillar"]} | {age / 24:.0f}d | {i["source"]} | {i.get("signal", "")} | {i["title"]} || {i["desc"][:260]}')


if __name__ == "__main__":
    main()
