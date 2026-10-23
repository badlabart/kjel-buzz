"""Missourinet articles on WireReady -> Claude's quick-read rewrite -> shown in place of the feed excerpt.

Boss (2026-10-23): every story card is a quick read. The Missourinet imports get the same format as the other apps;
stories typed in by Bruce, Jeff or Riley (B / J / R) and the LISTEN summaries are never touched. The feed text stays
in the Sheet; the rewrite goes in the "short" column and the page shows it under the bold headline.

List (nothing is posted):  python3 -I scripts/monet_short.py
  Prints each Missourinet article that has no rewrite yet:  id | added | headline || feed excerpt
Then Claude writes data/monet_short.json:
  [{"id": "51d92974", "text": "the rewrite"}]
Post them:                 python3 -I scripts/monet_short.py --post
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def call(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "text/plain;charset=utf-8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    try:
        url = json.loads((ROOT / "wireready" / "config.json").read_text())["url"]
    except (OSError, ValueError, KeyError):
        print("FAILED: wireready/config.json has no web app address")
        return
    if "--post" in sys.argv:
        path = ROOT / "data" / "monet_short.json"
        try:
            items = json.loads(path.read_text())
        except (OSError, ValueError):
            print("FAILED: data/monet_short.json is missing or not valid JSON")
            return
        done = 0
        for it in items:
            try:
                d = call(url, {"action": "rewrite", "id": it["id"], "text": it["text"]})
            except Exception as e:  # one bad post never stops the rest
                print(f"FAILED {it.get('id')}: {e}")
                continue
            # An older web app version ignores "rewrite" and still answers ok, so check the story really took it.
            if d.get("ok") and any(s["id"] == it["id"] and s.get("short") for s in d.get("stories", [])):
                done += 1
            elif d.get("ok"):
                print(f"FAILED {it.get('id')}: the live WireReady app has no rewrite action yet (redeploy Code.gs)")
            else:
                print(f"FAILED {it.get('id')}: {d.get('error')}")
        print(f"posted {done} of {len(items)} Missourinet rewrites")
        return
    try:
        d = call(url, {"action": "list"})
    except Exception as e:
        print(f"FAILED: {e}")
        return
    if not d.get("ok"):
        print(f"FAILED: {d.get('error')}")
        return
    todo = [s for s in d["stories"] if s["by"] == "MOnet" and s.get("kind") != "summary" and not s.get("short")]
    print(f"=== MISSOURINET TO REWRITE: {len(todo)}")
    for s in todo:
        head, _, rest = s["text"].partition("\n")
        print(f'{s["id"]} | {s["added"]} | {head} || {" ".join(rest.split())}')


if __name__ == "__main__":
    main()
