"""Candidates for the News app's LIGHT column (Boss 2026-10-21): uplifting, encouraging, amusing or funny stories
from the listening area. Any core-area town counts. No Lebanon percentage and no town priority.

Searches the area for feel-good and funny stories (14 days back), keeps the ones that pass the downer/politics
filters, fetches the article text so a card needs no click, and writes data/light_pool.json. Stories already in
data/pool.json (the LOCAL block) keep their ids, so build.py can find either. Separate from collect.py so a failure
here never blocks the Buzz.

Run: python3 -I scripts/light.py   (1-3 minutes)
"""
import json
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
import collect  # noqa: E402  (reuses pull(), the filters, town_of(), cluster(), link and text lookups)

LIGHT_DAYS = 14
# Google News ignores "when:" on a long query (it returned stories years old), so the tone words are split into
# short groups and "when:" goes first.
TONES = [
    '(heartwarming OR "feel-good" OR uplifting OR inspiring OR kindness OR generous)',
    '(surprise OR surprised OR reunited OR rescued OR adopted OR "pays it forward" OR "good deed")',
    '(funny OR hilarious OR viral OR adorable OR "made their day" OR "went the extra mile")',
]
AREAS = [
    '(Lebanon OR Laclede OR "Bennett Spring") Missouri',
    '("Lake of the Ozarks" OR "Osage Beach" OR Camdenton OR Eldon OR "Lake Ozark" OR Laurie OR "Sunrise Beach")',
    '(Waynesville OR "St. Robert" OR "Fort Leonard Wood" OR Richland OR Crocker OR Dixon)',
    '(Marshfield OR Seymour OR Rogersville OR Buffalo OR "Mountain Grove" OR Mansfield OR Hartville OR Norwood) Missouri',
    '(Bolivar OR Hermitage OR "Fair Grove" OR "Pleasant Hope" OR Iberia OR Tuscumbia) Missouri',
]
QUERIES = [f"{a} {t}" for a in AREAS for t in TONES] + [
    '(Ozarks OR "Laclede County" OR "Camden County" OR "Pulaski County" OR "Webster County" OR "Polk County" OR "Wright County") '
    '(dog OR cat OR horse OR puppy OR goat OR deer OR owl) (rescued OR reunited OR adopted OR adorable OR viral OR surprise)',
    '("Lebanon R-3" OR Waynesville OR Marshfield OR Camdenton OR Bolivar OR Buffalo OR "Mountain Grove") '
    '(students OR kids OR teacher OR "bus driver" OR coach) (surprise OR heartwarming OR kindness OR funny OR "made a difference" OR "went the extra mile")',
    '(Lebanon OR Camdenton OR Waynesville OR Marshfield OR Bolivar OR "Osage Beach" OR "Mountain Grove") Missouri '
    '("food drive" OR "toy drive" OR "coat drive" OR "giving back" OR "paid it forward" OR "community comes together" OR "neighbors help")',
    'Ozarks (funny OR hilarious OR quirky OR delightful OR "fun fact" OR laughs OR "best costume" OR "crowd favorite")',
    '"Lake of the Ozarks" (funny OR heartwarming OR "feel-good" OR unusual OR delightful OR "pays it forward")',
]


def gn_front(q, days):
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(f"when:{days}d {q}")
            + "&hl=en-US&gl=US&ceid=US:en")


def main():
    c = collect
    jobs = [("gn", "local", "Google News", gn_front(q, LIGHT_DAYS)) for q in QUERIES]
    # The searches find little (most feel-good hits are national), so every post from the area's own outlets
    # in the last 14 days is a candidate too. The main collector keeps only the top few per outlet and 7 days.
    jobs += [("feed", "local", l, u) for l, u in c.LOCAL_FEEDS]
    with ThreadPoolExecutor(6) as ex:
        raw = [it for chunk in ex.map(c.pull, jobs) for it in chunk]

    kept, dropped = [], {}
    for it in raw:
        if not it["title"] or (c.NOW - it["ts"]).total_seconds() > 24 * LIGHT_DAYS * 3600:
            continue
        why = c.blocked("local", it["title"], it["desc"], it["source"])
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        it["town"], it["tier"] = c.town_of(it["title"], it["desc"], it["source"])
        if it["town"] is None or it["tier"] == 2:  # Springfield, Branson etc. are outside the core listening area
            dropped["outside area"] = dropped.get("outside area", 0) + 1
            continue
        kept.append(it)

    items = c.cluster(kept)
    for it in items:
        it["id"] = "L" + md5((it["title"] + it["source"]).encode()).hexdigest()[:6]  # same id the LOCAL block would give it
    items.sort(key=lambda x: x["ts"], reverse=True)
    for it in items:
        it["gn_url"] = it["url"] if it["gn"] else None
    c.resolve_all(items, budget_s=150)
    c.summaries(items)
    c.bodies([i for i in items if not i["url"].startswith("https://news.google.com")])
    items = [i for i in items if not (c.TRAGIC.search(i["desc"][:200]) or c.POLITICS.search(i["desc"][:200]))]

    main_pool = json.loads((DATA / "pool.json").read_text())["items"] if (DATA / "pool.json").exists() else []
    in_local = {p["id"] for p in main_pool if p["col"] == "local"}
    fresh = [i for i in items if i["id"] not in in_local]
    both = [i for i in items if i["id"] in in_local]
    pool = [{k: i.get(k) for k in ("id", "title", "source", "url", "gn_url", "desc", "outlets", "town", "tier", "body")}
            | {"body": (i.get("body") or "")[:1800]}
            | {"col": "local", "ts": i["ts"].isoformat()} for i in fresh]
    (DATA / "light_pool.json").write_text(json.dumps({"collected": c.NOW.isoformat(), "items": pool}, indent=1, ensure_ascii=False))

    print(f"raw {len(raw)} | kept {len(items)} | new {len(fresh)} | also in the LOCAL block {len(both)} | dropped {dropped}")
    print("FAILED: " + (", ".join(c.FAILED) if c.FAILED else "none"))
    print("\n=== LIGHT (new candidates; the LOCAL block can also supply Light picks)")
    for i in fresh:
        age = (c.NOW - i["ts"]).total_seconds() / 3600
        age = f"{age:.0f}h" if age < 48 else f"{age / 24:.0f}d"
        full = (i.get("body") or i["desc"])[:450]  # the full text stays in data/light_pool.json for the lines
        print(f'{i["id"]} | {age} | {i["source"][:22]} [{i["town"]}{"*" if i["tier"] == 0 else ""}] | {i["title"]} || {full}')
    if both:
        print("\nAlso found by the Light searches and already in the LOCAL block: " + ", ".join(i["id"] for i in both))


if __name__ == "__main__":
    main()
