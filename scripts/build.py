"""Join data/picks.json (Claude's picks + lines) with data/pool.json -> data/buzz.js, index.html, docs/index.html.
Also writes music_search.js (top-40 archive + current music stories) next to each page for the artist search.

Run: python3 -I scripts/build.py
"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402  (reuses the Google News link lookup)
import concerts  # noqa: E402
import humor  # noqa: E402
import page  # noqa: E402
import wx  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# Boss (2026-10-19): Local and Morning News Only moved to a separate "News" app with the same look.
BUZZ = [("national", "National"), ("pride", "LOCAL PRIDE"), ("music", "Music"), ("humor", "Nat'l Day")]
NEWS = [("local", "Ozarks"), ("weird", "Morning News Only")]
COLUMNS = BUZZ + NEWS
# Boss (2026-10-21): the News app also carries LOCAL PRIDE (from the Buzz) and The Johnsons (from Show Prep), which
# stay on their original pages too. Her order: Johnsons, LOCAL PRIDE, Ozarks (the old "Local"), the new Light, and
# Morning News Only last.
NEWS_PAGE = ["wireready", "johnsons", "pride", "local", "light", "weird"]
# Boss (2026-10-22): WireReady, where the three news people paste wire stories and tap B, J or R when they use one.
# The column appears at the far left of News only after wireready/config.json holds the deployed Apps Script address.
WIREREADY_CFG = ROOT / "wireready" / "config.json"


def wireready_column():
    if not WIREREADY_CFG.exists():
        return None
    url = json.loads(WIREREADY_CFG.read_text()).get("url", "")
    if not url.startswith("http"):
        return None
    return {"key": "wireready", "name": "WireReady", "cards": [], "wireready_url": url}
# Boss (2026-10-20): "Show Prep" = LOCAL PRIDE, National, Humor, Music, then every Event Board column
# except KIM ONLY and Live Music.
SHOW_PREP = ["pride", "national", "humor", "music", "timely", "johnsons"]
EXTRA_NAMES = {"timely": "Timely", "johnsons": "The Johnsons"}
EVENTS_JS = Path.home() / "Documents/Claude/Projects/KJEL-event-board/data/events.js"
EVENT_SKIP = {"kim only", "live music", "manual entries"}  # manual entries are filed under their own category (d["manual"])


def event_columns():
    """Event Board columns for Show Prep, upcoming only, soonest first."""
    if not EVENTS_JS.exists():
        return []
    d = json.loads(EVENTS_JS.read_text().split("=", 1)[1].rstrip().rstrip(";"))
    today = datetime.now(collect.CT).date()
    cols = []
    for typ in d["types"]:
        if typ.lower() in EVENT_SKIP:
            continue
        # Boss (2026-10-21): events she adds by hand go into the Show Prep category they belong in (d["manual"]).
        evs = sorted((e for e in d["events"] + d.get("manual", []) if e["type"] == typ and date.fromisoformat(e["date"]) >= today),
                     key=lambda e: (e["date"], e.get("min", 0)))
        cards = [{"kind": "event", "title": e["title"], "line": e["title"], "city": e["town"], "source": e.get("source", ""),
                  "url": e["url"], "ts": None, "signal": "", "why": e.get("why", ""), "place": e.get("place", ""),
                  "date": e["date"], "time": e.get("time", ""),
                  "when_label": date.fromisoformat(e["date"]).strftime("%a, %b %-d").upper()} for e in evs]
        cols.append({"key": "ev-" + typ.lower().replace(" ", "-"), "name": typ, "cards": cards})
    return cols

def extra_columns():
    """Timely and The Johnsons (Boss 2026-10-21). Candidates come from data/extra_pool.json (scripts/extra.py), the picks
    and lines from data/picks_extra.json. Timely cards are dated, so the page hides them once their day has passed."""
    pool_p, picks_p = DATA / "extra_pool.json", DATA / "picks_extra.json"
    if not (pool_p.exists() and picks_p.exists()):
        return {}
    pool = json.loads(pool_p.read_text())
    items = {i["id"]: i for i in pool["timely"] + pool["johnsons"]}
    picks = json.loads(picks_p.read_text())
    cols = {}
    for key in ("timely", "johnsons"):
        cards = []
        for p in picks.get(key, []):
            it = items.get(p["id"])
            if not it:
                continue
            line = p.get("line") or it.get("line", "")
            if key == "timely":
                d = date.fromisoformat(p.get("date") or it["date"])
                cards.append({"kind": "timely", "title": line, "line": line, "label": p.get("label") or it.get("label", ""),
                              "city": "", "source": it["source"], "url": it["url"], "ts": None, "signal": "",
                              "date": d.isoformat(), "when_label": d.strftime("%a, %b %-d").upper()})
            else:
                cards.append({"id": it["id"], "title": it["title"], "line": line, "label": p.get("label") or it["pillar"], "city": "",
                              "source": it["source"], "url": it["url"], "ts": it["ts"], "signal": it.get("signal", "")})
        if key == "timely":
            cards.sort(key=lambda c: c["date"])  # stable: pick order holds within a day
        cols[key] = {"key": key, "name": EXTRA_NAMES[key], "cards": cards}
    return cols


def light_column(pool, picks):
    """Light (Boss 2026-10-21): uplifting, encouraging, amusing or funny stories from anywhere in the listening area,
    no Lebanon percentage. Candidates come from data/light_pool.json (scripts/light.py) or the main pool; Claude writes
    data/picks_light.json. A story LOCAL PRIDE, National or Morning News Only already carries stays there."""
    picks_p, pool_p = DATA / "picks_light.json", DATA / "light_pool.json"
    items = dict(pool)
    if pool_p.exists():
        items.update({i["id"]: i for i in json.loads(pool_p.read_text())["items"]})
    taken = {p["id"] for k in ("national", "pride", "weird") for p in picks.get(k, [])}
    cards, missing = [], []
    for p in (json.loads(picks_p.read_text()).get("light", []) if picks_p.exists() else []):
        it = items.get(p["id"])
        if p["id"] in taken:
            continue
        if not it:
            missing.append(p["id"])
            continue
        cards.append(dict(it, line=p.get("line", ""), city=p.get("city", ""), label="", congrats=False))
    return {"key": "light", "name": "Light", "cards": cards}, missing


def record_extra_shown(cols):
    """The Johnsons never repeat: remember what was shown so scripts/extra.py skips it for 60 days."""
    path = DATA / "extra_shown.json"
    seen = json.loads(path.read_text()) if path.exists() else {}
    for c in cols.get("johnsons", {}).get("cards", []):
        seen[c["id"]] = datetime.now(collect.CT).date().isoformat()
    keep = {k: v for k, v in seen.items() if (datetime.now(collect.CT).date() - date.fromisoformat(v)).days <= 60}
    path.write_text(json.dumps(keep, indent=0))


SPLIT = ("pride", "local")  # columns that aim for 50% Lebanon
LEBANON_GOAL = 0.50


def music_search():
    """Kept top-40 stories plus this run's other music stories, newest first, as one lazy-loaded script."""
    arch = json.loads((DATA / "music_archive.json").read_text()) if (DATA / "music_archive.json").exists() else []
    recent = json.loads((DATA / "music_recent.json").read_text()) if (DATA / "music_recent.json").exists() else []
    rows = sorted(arch + recent, key=lambda e: e["d"], reverse=True)
    body = "window.KJEL_MUSIC = " + json.dumps(rows, separators=(",", ":"), ensure_ascii=True) + ";\n"
    for folder in (ROOT, ROOT / "docs", ROOT / "show-prep", ROOT / "docs" / "show-prep"):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "music_search.js").write_text(body)
    return len(arch), len(recent)


MUSIC_KEEP_DAYS = 30
MUSIC_MAX = 30  # news cards; concerts come on top of these


def music_column(picks, pool):
    """Music news stays up to 30 days. Each day's picks are added; picks["music_drop"] removes cards that a
    better or more local story replaced. Concerts by top-40 artists sit on top until the show date passes."""
    path = DATA / "music_board.json"
    board = json.loads(path.read_text()) if path.exists() else []
    today = datetime.now(collect.CT).date()
    drop = set(picks.get("music_drop", []))
    board = [c for c in board if c["id"] not in drop
             and (today - date.fromisoformat(c["added"])).days <= MUSIC_KEEP_DAYS]
    have = {c["id"]: c for c in board}
    missing = []
    for p in reversed(picks.get("music", [])):  # reversed so the first pick ends up on top
        it = pool.get(p["id"])
        if p["id"] in have:
            have[p["id"]].update(line=p.get("line", have[p["id"]]["line"]), city=p.get("city", have[p["id"]].get("city", "")))
            continue
        if not it:
            missing.append(p["id"])
            continue
        card = {k: it.get(k) for k in ("id", "title", "source", "url", "ts", "signal", "near")}
        card.update(line=p.get("line", ""), city=p.get("city", ""), added=today.isoformat())
        board.insert(0, card)
        have[card["id"]] = card
    # Over the cap: drop the oldest cards that are not tied to our area first.
    while len(board) > MUSIC_MAX:
        far = [c for c in board if not c.get("near")] or board
        board.remove(min(far, key=lambda c: c["added"]))
    board.sort(key=lambda c: (c.get("near") or 9, -date.fromisoformat(c["added"]).toordinal()))
    path.write_text(json.dumps(board, indent=1, ensure_ascii=False))

    shows = json.loads((DATA / "concerts.json").read_text()) if (DATA / "concerts.json").exists() else []
    gigs = []
    for sh in shows:
        d = date.fromisoformat(sh["date"])
        if d < today:
            continue
        gigs.append({"id": "C" + sh["key"][:20], "kind": "concert", "title": sh["event"], "source": "AllEvents",
                     "url": sh["url"], "ts": None, "signal": f'{sh["artist"]}: #{sh["rank"]} on Country Airplay',
                     "line": concerts.sentence(sh, d),
                     "city": sh["city"], "date": sh["date"], "when_label": d.strftime("%a, %b %-d").upper()})
    return gigs + board, missing


def main():
    pool = {i["id"]: i for i in json.loads((DATA / "pool.json").read_text())["items"]}
    picks = json.loads((DATA / "picks.json").read_text())
    cols, missing = [], []
    for key, name in COLUMNS:
        if key == "music":
            cards, gone = music_column(picks, pool)
            missing += gone
            cols.append({"key": key, "name": name, "cards": cards})
            continue
        cards = []
        for p in picks.get(key, []):
            it = pool.get(p["id"])
            if not it:
                missing.append(p["id"])
                continue
            cards.append(dict(it, line=p.get("line", ""), city=p.get("city", ""), label=p.get("label", ""),
                              congrats=False))  # LOCAL PRIDE is all congratulations, so no tag is needed
        if key == "humor":  # today's national days and bits first, then the coming week's days in date order
            today = datetime.now(collect.CT).date().isoformat()
            ahead = sorted((c for c in cards if c.get("kind") == "day" and (c.get("date") or today) > today),
                           key=lambda c: c["date"])
            cards = [c for c in cards if c not in ahead] + ahead
        cols.append({"key": key, "name": name, "cards": cards})

    light, gone = light_column(pool, picks)
    missing += gone
    light_ids = {c["id"] for c in light["cards"]}
    for col in cols:  # a story sits in one column: Light wins over Ozarks
        if col["key"] == "local":
            col["cards"] = [c for c in col["cards"] if c.get("id") not in light_ids]

    every = [c for col in cols + [light] for c in col["cards"] if c.get("kind") != "concert"]
    collect.resolve_all(every, budget_s=120)
    unresolved = sum(1 for c in every if c["url"].startswith("https://news.google.com"))

    lebanon = {}
    for col in cols:
        if col["key"] in SPLIT:
            n = sum(1 for c in col["cards"] if (c.get("city") or "").lower() == "lebanon"
                    or (not c.get("city") and c.get("tier") == 0))
            lebanon[col["key"]] = {"count": n, "of": len(col["cards"]), "goal": LEBANON_GOAL}
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    by_key = {c["key"]: c for c in cols}
    by_key["light"] = light
    extras = extra_columns()
    by_key.update(extras)
    wrcol = wireready_column()
    if wrcol:
        by_key["wireready"] = wrcol
    buzz_keys = {k for k, _ in BUZZ}
    buzz = {"updated": stamp, "columns": [c for c in cols if c["key"] in buzz_keys],
            "lebanon": {k: v for k, v in lebanon.items() if k in buzz_keys}}
    news = {"updated": stamp, "columns": [by_key[k] for k in NEWS_PAGE if k in by_key],
            "lebanon": {k: v for k, v in lebanon.items() if k in NEWS_PAGE}}
    (DATA / "buzz.js").write_text("window.KJEL_BUZZ = " + json.dumps(buzz, indent=1, ensure_ascii=False) + ";\n")
    (DATA / "news.js").write_text("window.KJEL_NEWS = " + json.dumps(news, indent=1, ensure_ascii=False) + ";\n")
    kept, recent = music_search()
    page.write(buzz)
    page.write(news, title="News", doc_title="KJEL News", subdir="news")
    # Boss (2026-10-21): News lives at its own short address, badlabart.github.io/kjel-news
    news_out = Path.home() / "Documents/Claude/Projects/KJEL-news/docs"
    if news_out.parent.exists():
        news_out.mkdir(exist_ok=True)
        (news_out / "index.html").write_bytes((ROOT / "docs" / "news" / "index.html").read_bytes())
    # Boss (2026-10-21): Show Prep opens with a day / date search, and Wx (alerts + today's town forecasts) is its first column.
    wxcol = wx.column()
    prep = {"updated": stamp, "columns": [wxcol] + [by_key[k] for k in SHOW_PREP if k in by_key] + event_columns(),
            "lebanon": {k: v for k, v in lebanon.items() if k in SHOW_PREP}}
    page.write(prep, title="Show Prep", doc_title="KJEL Show Prep", subdir="show-prep", day_search=True)
    # Boss (2026-10-20): Show Prep also lives at its own short address, badlabart.github.io/kjel-showprep
    out = Path.home() / "Documents/Claude/Projects/KJEL-showprep/docs"
    if out.parent.exists():
        out.mkdir(exist_ok=True)
        for f in ("index.html", "music_search.js"):
            (out / f).write_bytes((ROOT / "docs" / "show-prep" / f).read_bytes())
    record_extra_shown(extras)
    humor.record_shown(collect, [c for c in next(c for c in cols if c["key"] == "humor")["cards"] if c.get("kind") == "joke"])
    print(f"Board: {' | '.join(f'{c[1]} {len(x["cards"])}' for c, x in zip(COLUMNS, cols))} | "
          f"Light {len(light['cards'])} | "
          f"Lebanon: {' / '.join(f'{k} {v["count"]} of {v["of"]}' for k, v in lebanon.items())} | "
          f"music search: {kept} kept + {recent} current | "
          f"Wx: {wxcol['count']} alerts{' | Wx failed: ' + '; '.join(wxcol['failed']) if wxcol['failed'] else ''} | "
          f"Google links left unresolved: {unresolved} | missing pick ids: {', '.join(missing) or 'none'}")


if __name__ == "__main__":
    main()
