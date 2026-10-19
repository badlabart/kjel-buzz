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

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# Boss (2026-10-19): Local and Morning News Only moved to a separate "News" app with the same look.
BUZZ = [("national", "National"), ("pride", "LOCAL PRIDE"), ("music", "Music"), ("humor", "Humor")]
NEWS = [("local", "Local"), ("weird", "Morning News Only")]
COLUMNS = BUZZ + NEWS
SPLIT = ("pride", "local")  # columns that aim for 50% Lebanon
LEBANON_GOAL = 0.50


def music_search():
    """Kept top-40 stories plus this run's other music stories, newest first, as one lazy-loaded script."""
    arch = json.loads((DATA / "music_archive.json").read_text()) if (DATA / "music_archive.json").exists() else []
    recent = json.loads((DATA / "music_recent.json").read_text()) if (DATA / "music_recent.json").exists() else []
    rows = sorted(arch + recent, key=lambda e: e["d"], reverse=True)
    body = "window.KJEL_MUSIC = " + json.dumps(rows, separators=(",", ":"), ensure_ascii=True) + ";\n"
    for folder in (ROOT, ROOT / "docs"):
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
                     "city": sh["city"], "when_label": d.strftime("%a, %b %-d").upper()})
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
        cols.append({"key": key, "name": name, "cards": cards})

    every = [c for col in cols for c in col["cards"] if c.get("kind") != "concert"]
    collect.resolve_all(every, budget_s=120)
    unresolved = sum(1 for c in every if c["url"].startswith("https://news.google.com"))

    lebanon = {}
    for col in cols:
        if col["key"] in SPLIT:
            n = sum(1 for c in col["cards"] if (c.get("city") or "").lower() == "lebanon"
                    or (not c.get("city") and c.get("tier") == 0))
            lebanon[col["key"]] = {"count": n, "of": len(col["cards"]), "goal": LEBANON_GOAL}
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    buzz_keys, news_keys = {k for k, _ in BUZZ}, {k for k, _ in NEWS}
    buzz = {"updated": stamp, "columns": [c for c in cols if c["key"] in buzz_keys],
            "lebanon": {k: v for k, v in lebanon.items() if k in buzz_keys}}
    news = {"updated": stamp, "columns": [c for c in cols if c["key"] in news_keys],
            "lebanon": {k: v for k, v in lebanon.items() if k in news_keys}}
    (DATA / "buzz.js").write_text("window.KJEL_BUZZ = " + json.dumps(buzz, indent=1, ensure_ascii=False) + ";\n")
    (DATA / "news.js").write_text("window.KJEL_NEWS = " + json.dumps(news, indent=1, ensure_ascii=False) + ";\n")
    kept, recent = music_search()
    page.write(buzz)
    page.write(news, title="News", doc_title="KJEL News", subdir="news")
    humor.record_shown(collect, [c for c in next(c for c in cols if c["key"] == "humor")["cards"] if c.get("kind") == "joke"])
    print(f"Board: {' | '.join(f'{c[1]} {len(x["cards"])}' for c, x in zip(COLUMNS, cols))} | "
          f"Lebanon: {' / '.join(f'{k} {v["count"]} of {v["of"]}' for k, v in lebanon.items())} | "
          f"music search: {kept} kept + {recent} current | "
          f"Google links left unresolved: {unresolved} | missing pick ids: {', '.join(missing) or 'none'}")


if __name__ == "__main__":
    main()
