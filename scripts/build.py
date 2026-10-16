"""Join data/picks.json (Claude's picks + lines) with data/pool.json -> data/buzz.js, index.html, docs/index.html.

Run: python3 -I scripts/build.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402  (reuses the Google News link lookup)
import page  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
COLUMNS = [("national", "National"), ("local", "Local"), ("music", "Music")]
LEBANON_GOAL = 0.30


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
    page.write(data)
    print(f"Board: {' | '.join(f'{c[1]} {len(x["cards"])}' for c, x in zip(COLUMNS, cols))} | "
          f"Lebanon {leb} of {len(local)} | Google links left unresolved: {unresolved} | "
          f"missing pick ids: {', '.join(missing) or 'none'}")


if __name__ == "__main__":
    main()
