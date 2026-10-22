"""Missourinet LISTEN stories that mention Lebanon -> transcript for Claude to summarize -> summary on WireReady.

Boss (2026-10-22): WireReady carries Missourinet ARTICLES only. A LISTEN feature (audio interview) that specifically
mentions Lebanon is the one exception: it is transcribed here and only a written SUMMARY goes on WireReady. The audio
and the transcript stay in a temporary folder and are deleted; neither is ever saved in this repo or posted.

Summary format (Boss): an instantly engaging first sentence that teases what is coming, the core details (only the
essentials the Johnsons care about), and a last sentence with the outcome, what's next, or something uplifting. Never
end on a downer.

Run (nothing is posted):   python3 -I scripts/monet_listen.py
  Prints each new Lebanon LISTEN story with its transcript, and saves data/monet_listen_pending.json (links + dates).
Then Claude writes data/monet_listen_summaries.json:
  [{"link": "https://www.missourinet.com/...", "text": "the summary"}]
Post them:                 python3 -I scripts/monet_listen.py --post
  Sends each summary to the WireReady web app (wireready/config.json) and marks the story done.
Metadata only (no audio):  python3 -I scripts/monet_listen.py --list

Only stories whose title, blurb or tags say "Lebanon" are caught. A story that mentions Lebanon only inside the audio
would need every LISTEN story transcribed.
"""
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CT = ZoneInfo("America/Chicago")
FEED = "https://www.missourinet.com/feed/"
# Missourinet's firewall refuses scripts that look like scripts, so ask like a browser (same as wireready/Code.gs).
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
CRAWL_DELAY = 30  # robots.txt asks for 30 seconds between requests
DONE = DATA / "monet_listen_done.json"
PENDING = DATA / "monet_listen_pending.json"
SUMMARIES = DATA / "monet_listen_summaries.json"
WHISPER_TIMEOUT_S = 40 * 60


def get(url, binary=False, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
                                               "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        return (data, r.headers.get("Content-Type", "")) if binary else data.decode("utf-8", "ignore")


def text_of(s):
    s = re.sub(r"^\s*<!\[CDATA\[|\]\]>\s*$", "", s or "")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def is_listen(title, link, audio):
    """Same rule as isListen_ in wireready/Code.gs."""
    return bool(audio or re.search(r"\(\s*listen\s*\)", title, re.I) or re.search(r"-listen/?$", link, re.I)
                or "sports-report" in link.lower())


def parse_feed(xml):
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        def tag(t):
            m = re.search(rf"<{t}[^>]*>(.*?)</{t}>", it, re.S)
            return m.group(1) if m else ""
        title, link = text_of(tag("title")), text_of(tag("link"))
        try:
            pub = parsedate_to_datetime(text_of(tag("pubDate")))
        except Exception:
            continue
        cats = [text_of(c) for c in re.findall(r"<category[^>]*>(.*?)</category>", it, re.S)]
        audio = bool(re.search(r"<enclosure[^>]+(audio/|\.mp3|\.m4a)", it, re.I))
        out.append({"title": title, "link": link, "pub": pub, "excerpt": text_of(tag("description")), "cats": cats,
                    "listen": is_listen(title, link, audio)})
    return out


def mentions_lebanon(it):
    return bool(re.search(r"\bLebanon\b", " ".join([it["title"], it["excerpt"]] + it["cats"])))


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def candidates():
    feed = parse_feed(get(FEED))
    done = load(DONE, {})
    return [it for it in feed if it["listen"] and mentions_lebanon(it) and it["link"] not in done], len(feed)


def audio_url(article_html):
    """The audio player on a LISTEN page is an Art19 embed; Art19 serves every episode as an mp3."""
    m = re.search(r"art19\.com/shows/[0-9a-f-]+/episodes/([0-9a-f-]{36})", article_html)
    return f"https://rss.art19.com/episodes/{m.group(1)}.mp3" if m else None


def transcribe(it, work):
    time.sleep(CRAWL_DELAY)  # be polite to the site before the second request
    page = get(it["link"])
    url = audio_url(page)
    if not url:
        raise RuntimeError("no audio player found on the page")
    data, ctype = get(url, binary=True, timeout=180)
    if "audio" not in ctype or len(data) < 100_000:
        raise RuntimeError(f"audio download looked wrong ({ctype}, {len(data)} bytes)")
    mp3 = work / "story.mp3"
    mp3.write_bytes(data)
    if not shutil.which("whisper"):
        raise RuntimeError("whisper is not installed")
    subprocess.run(["whisper", str(mp3), "--model", "turbo", "--language", "en", "--fp16", "False",
                    "--output_format", "txt", "--output_dir", str(work), "--verbose", "False"],
                   check=True, capture_output=True, timeout=WHISPER_TIMEOUT_S)
    return (work / "story.txt").read_text().strip()


def main_prepare(list_only):
    try:
        found, n = candidates()
    except Exception as e:
        print(f"FAILED: could not read the Missourinet feed ({str(e)[:80]})")
        return 1
    print(f"Missourinet feed: {n} items | LISTEN stories mentioning Lebanon, not yet done: {len(found)}")
    pending = []
    for it in found:
        when = it["pub"].astimezone(CT)
        head = f'{it["title"]} | {it["link"]} | {when:%Y-%m-%d %H:%M} CT | tags: {", ".join(it["cats"][:6])}'
        if list_only:
            print("CANDIDATE:", head)
            continue
        work = Path(tempfile.mkdtemp(prefix="monet_listen_"))
        try:
            transcript = transcribe(it, work)
            pending.append({"link": it["link"], "title": it["title"], "added": f"{when:%Y-%m-%d %H:%M}"})
            print(f"\n=== TRANSCRIBE-AND-SUMMARIZE: {head}\n{transcript}\n=== END")
        except Exception as e:
            print(f"FAILED to transcribe {it['link']} ({str(e)[:100]})")
        finally:
            shutil.rmtree(work, ignore_errors=True)  # audio and transcript never stay on disk
    if not list_only:
        PENDING.write_text(json.dumps(pending, indent=1))
    return 0


def clean_title(t):
    return re.sub(r"\s*\(\s*listen\s*\)\s*", "", t, flags=re.I).strip()


def main_post():
    pending = {p["link"]: p for p in load(PENDING, [])}
    summaries = load(SUMMARIES, [])
    cfg = load(ROOT / "wireready" / "config.json", {})
    if not cfg.get("url"):
        print("FAILED: wireready/config.json has no web app address")
        return 1
    done, posted = load(DONE, {}), 0
    for s in summaries:
        p = pending.get(s["link"])
        if not p or s["link"] in done:
            continue
        body = json.dumps({"action": "summary", "title": clean_title(p["title"]), "text": s["text"].strip(),
                           "link": s["link"], "added": p["added"]}).encode()
        req = urllib.request.Request(cfg["url"], data=body, headers={"Content-Type": "text/plain;charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                reply = json.loads(r.read().decode())
        except Exception as e:
            print(f"FAILED to post {s['link']} ({str(e)[:80]})")
            continue
        if reply.get("ok"):
            done[s["link"]] = datetime.now(CT).date().isoformat()
            posted += 1
            print(f"posted: {clean_title(p['title'])}")
        else:
            print(f"FAILED to post {s['link']} (server said: {reply.get('error')})")
    DONE.write_text(json.dumps(done, indent=1))
    SUMMARIES.unlink(missing_ok=True)  # the summaries now live on WireReady
    print(f"posted {posted} of {len(summaries)} summaries")
    return 0


if __name__ == "__main__":
    if "--post" in sys.argv:
        sys.exit(main_post())
    sys.exit(main_prepare("--list" in sys.argv))
