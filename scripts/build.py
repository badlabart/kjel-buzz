"""Join data/picks.json (Claude's picks + lines) with data/pool.json -> data/buzz.js, index.html, docs/index.html.
Also writes music_search.js (top-40 archive + current music stories) next to each page for the artist search.

Run: python3 -I scripts/build.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402  (reuses the Google News link lookup)
import humor  # noqa: E402
import page  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
COLUMNS = [("national", "National"), ("local", "Local"), ("music", "Music"), ("humor", "Humor")]
LEBANON_GOAL = 0.30


def music_search():
    """Kept top-40 stories plus this run's other music stories, newest first, as one lazy-loaded script."""
    arch = json.loads((DATA / "music_archive.json").read_text()) if (DATA / "music_archive.json").exists() else []
    recent = json.loads((DATA / "music_recent.json").read_text()) if (DATA / "music_recent.json").exists() else []
    rows = sorted(arch + recent, key=lambda e: e["d"], reverse=True)
    body = "window.KJEL_MUSIC = " + json.dumps(rows, separators=(",", ":"), ensure_ascii=True) + ";\n"
    for folder in (ROOT, ROOT / "docs"):
        (folder / "music_search.js").write_text(body)
    return len(arch), len(recent)


def main():
    pool = {i["id"]: i for i in json.loads((DATA / "pool.json").read_text())["items"]}
    picks = json.loads((DATA / "picks.json").read_text())
    cols, missing = [], []
    for key, name in COLUMNS:
        cards = []
        for p in picks.get(key, []):
            it = pool.get(p["id"])
            if not it:
                missing.append(p["id"])
                continue
            cards.append(dict(it, line=p.get("line", "")))
        cols.append({"key": key, "name": name, "cards": cards})

    every = [c for col in cols for c in col["cards"]]
    collect.resolve_all(every)
    unresolved = sum(1 for c in every if c["url"].startswith("https://news.google.com"))

    local = next(c for c in cols if c["key"] == "local")["cards"]
    leb = sum(1 for c in local if c.get("tier") == 0)
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "columns": cols,
            "lebanon": {"count": leb, "of": len(local), "goal": LEBANON_GOAL}}
    (DATA / "buzz.js").write_text("window.KJEL_BUZZ = " + json.dumps(data, indent=1, ensure_ascii=False) + ";\n")
    kept, recent = music_search()
    page.write(data)
    humor.record_shown(collect, [c for c in next(c for c in cols if c["key"] == "humor")["cards"] if c.get("kind") == "joke"])
    print(f"Board: {' | '.join(f'{c[1]} {len(x["cards"])}' for c, x in zip(COLUMNS, cols))} | "
          f"Lebanon {leb} of {len(local)} | music search: {kept} kept + {recent} current | "
          f"Google links left unresolved: {unresolved} | missing pick ids: {', '.join(missing) or 'none'}")


if __name__ == "__main__":
    main()
