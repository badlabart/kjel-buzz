#!/usr/bin/env python3
"""Story Editor worker (Boss 2026-11-03). Runs every minute on Boss's Mac (launchd: com.bosslady.kjel-editor).

Asks the WireReady Apps Script for queued stories, rewrites each one with Claude Code (`claude -p`, on Boss's Claude
plan: no API key, no extra bill) using her style guide, and sends the result back. When nothing is queued it makes one
small web request and exits, so Claude is only called when J or R taps Condense or Add more detail.

The style guide (her rules + before/after samples) is wireready/style_prompt.txt: gitignored, because the samples name
real people and this repo is public.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
STYLE = ROOT / "wireready" / "style_prompt.txt"
CT = ZoneInfo("America/Chicago")
CLAUDE = os.environ.get("KJEL_CLAUDE_BIN", "/usr/local/bin/claude")
WORKDIR = Path.home() / "Library" / "Application Support" / "kjel-editor"  # no CLAUDE.md here, so none is picked up
FAILS = WORKDIR / "fails.json"  # tries per story id, so one bad story never calls Claude every minute forever
MAX_TRIES = 3

MORE = ("Add more detail from the source to the broadcast version. Add only the details most important to our core "
        "listening area. Nothing graphic, and nothing a listener cannot take in the moment it is heard. Keep the same style, "
        "the tease and the ending. Stay at or under 45 seconds (about 120 words). If the source has nothing more worth adding, "
        "return the current version unchanged with status \"ok\".")


def call(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "text/plain;charset=utf-8"})
    with urllib.request.urlopen(req, timeout=60) as r:  # Apps Script answers with a redirect; urllib follows it
        d = json.loads(r.read().decode())
    if not d.get("ok"):
        raise RuntimeError(d.get("error") or "WireReady said no")
    return d


def prompt_for(item):
    day = datetime.strptime(item["added"][:10], "%Y-%m-%d").strftime("%A, %B %-d, %Y")
    head = f"Today is {day} (the day this story was entered). Use it to turn dates into days of the week.\n\n"
    if item["status"] == "more":
        return (head + "Here is the source story:\n\n" + item["source"] + "\n\nHere is the current broadcast version:\n\n"
                + item["story"] + "\n\n" + MORE)
    return head + "Rewrite this story:\n\n" + item["source"]


def claude(prompt, system):
    # A clean call: Boss's own system prompt only, no tools, no settings, hooks or MCP servers, nothing saved.
    WORKDIR.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([CLAUDE, "-p", prompt, "--system-prompt", system, "--tools", "", "--setting-sources", "",
                        "--strict-mcp-config", "--no-session-persistence", "--output-format", "json", "--model", "opus"],
                       cwd=WORKDIR, capture_output=True, text=True, timeout=300)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        raise RuntimeError((r.stderr or r.stdout or "claude gave no answer").strip()[:300])
    if d.get("is_error"):
        raise RuntimeError(str(d.get("result") or "claude error")[:300])
    text = str(d.get("result") or "")
    m = re.search(r"\{.*\}", text, re.S)  # the JSON object, even if Claude wraps it in a code fence
    if not m:
        raise RuntimeError("no JSON in Claude's answer: " + text[:200])
    out = json.loads(m.group(0))
    if out.get("status") not in ("ok", "blocked"):
        raise RuntimeError("bad status: " + str(out.get("status")))
    return out


def main():
    url = os.environ.get("KJEL_WR_URL") or json.loads((ROOT / "wireready" / "config.json").read_text())["url"]
    queue = call(url, {"action": "queue"})["queue"]
    if not queue:
        return 0
    system = STYLE.read_text()
    fails = json.loads(FAILS.read_text()) if FAILS.exists() else {}
    for item in queue:
        stamp = datetime.now(CT).strftime("%Y-%m-%d %H:%M")
        try:
            out = claude(prompt_for(item), system)
            call(url, {"action": "done", "id": item["id"], "status": out["status"], "story": out.get("story", ""),
                       "reason": out.get("reason", "")})
            print(f"{stamp} {item['id']} {item['status']} -> {out['status']}", flush=True)
            fails.pop(item["id"], None)
        except Exception as e:  # leave it queued; the next run tries again, up to MAX_TRIES
            fails[item["id"]] = fails.get(item["id"], 0) + 1
            print(f"{stamp} {item['id']} FAILED ({fails[item['id']]}): {e}", file=sys.stderr, flush=True)
            if fails[item["id"]] >= MAX_TRIES:
                try:
                    call(url, {"action": "done", "id": item["id"], "status": "blocked", "story": "",
                               "reason": "Claude could not edit this story. Paste it again, or edit it by hand."})
                    fails.pop(item["id"], None)
                except Exception as e2:
                    print(f"{stamp} {item['id']} could not mark failed: {e2}", file=sys.stderr, flush=True)
    WORKDIR.mkdir(parents=True, exist_ok=True)
    FAILS.write_text(json.dumps(fails))
    return 0


if __name__ == "__main__":
    sys.exit(main())
