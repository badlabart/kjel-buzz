# WireReady (News app, far-left column + full page)

Boss 2026-10-22. LIVE: https://badlabart.github.io/kjel-news/ (column) and https://badlabart.github.io/kjel-news/wireready/ (full page).

## What it is
- Column on News: small "Full page" button, "+ Add Story", newest 20 stories, "+N more" link.
- Full page: MOnet (Missourinet), Bruce, Jeff, Riley (stories B, J and R entered). Columns scroll on their own.
- Add Story: the person checks B, J or R (required), pastes the story, Submit. It lands on top with a tiny "added Oct 22".
- The first line of a story is bold (every Missourinet headline, and any typed story with more than one line).
- B / J / R letters on every story: tap = used (tiny date shows under the story), tap again = undo.
- Every tap is logged by date in the Google Sheet (`Taps` tab) and emailed weekly.
- NO PASSCODE (removed by Boss 2026-10-22): anyone with the page address can read, add and tap. WireReady menu in the Sheet > Set passcode brings it back; the pages then show an Unlock box by themselves.

## What lives where
- `Code.gs`: Google Apps Script web app inside the private Google Sheet "WireReady" (Boss's Google account). `appsscript.json` is reference only.
- Sheet tabs: `Stories` (id, added, text, by, link, kind), `Taps` (tapped, who, story added, story text, story id, story from).
- `config.json`: the deployed web app address. Delete it to switch WireReady off.
- `scripts/page.py` (WR_* constants) draws both pages; `scripts/build.py` (`wireready_column`, `wireready_full`) adds them.
- NEVER in this repo (it is public): stories typed by staff, the weekly email address, any passcode. They live in the Sheet and in Script properties.

## Missourinet rules (Boss 2026-10-22: articles only)
- Daily about 4 AM Central (Apps Script trigger, runs on Google's servers): `importMonet` adds new ARTICLES from https://www.missourinet.com/feed/ (headline + ~60-word excerpt + link). Only the newest 20 items are reachable (page 2 of the feed is blocked by the site's firewall) and about a quarter of them are articles.
- Never imported: "LISTEN" features and audio reports (title has "(LISTEN)", link ends in "-listen", audio enclosure, or "sports-report" in the link). `importMonet` also deletes any that an earlier import let in.
- Exception: a LISTEN story that specifically mentions Lebanon (title, blurb or tags) is transcribed and only a SUMMARY is posted, `kind = summary`, tagged "audio summary". Done by the 6 AM Claude task (steps 1d and 2d) with `scripts/monet_listen.py`: it finds the story, downloads the Art19 audio, transcribes with local Whisper (`turbo`), prints the transcript for Claude to summarize, and deletes the audio and transcript. `--post` sends the summary to the web app; `--list` only lists candidates.
- Summary format (Boss): an instantly engaging first sentence that teases what is coming, the core details (only what the Johnsons care about), a last sentence with the outcome, what's next, or something uplifting. Never ends on a downer.
- The site's robots.txt asks for 30 seconds between requests; the script waits 30 s before its second request. Full text of articles is not fetched (the site rate-limits quick fetches).
- Gap: a Lebanon mention that exists only inside the audio is missed; catching it would mean transcribing every LISTEN story (about a dozen a day).

## Schedules
- Apps Script (Google's servers): `importMonet` daily ~4 AM, `weeklyLog` Mondays ~6 AM Central (emails the Monday-to-Sunday that just ended, taps grouped by day, full story text; a week with no taps still sends one line).
- Claude 6 AM task on the Mac: `monet_listen.py` steps 1d / 2d.

## Menu in the Sheet (WireReady menu)
Set passcode, Remove passcode, Set weekly email address, Import Missourinet stories now, Send last week's log now.

## Changing the script
1. Edit `Code.gs` here, run the node tests, push.
2. In the Sheet: Extensions > Apps Script, paste the new Code.gs, save.
3. Run `setup` (refreshes header rows), then `selfTest`: it must log SELF TEST PASSED.
4. Deploy > Manage deployments > edit (pencil) > Version: New version > Deploy. The web app address stays the same (the change can take a few minutes to reach the live address).

## Gotchas learned
- Sheets turns text starting with "=" into a formula even in a text-formatted cell; every cell is written with a leading apostrophe (`appendText_`). The real-Google `selfTest` caught it; the mock could not.
- A POST with Content-Type text/plain avoids the CORS preflight, so the page can call the script from github.io (verified live).
- GitHub Pages can take 10+ minutes to serve a new build; compare the "updated" stamp in the page header.
- Stories drop off the page after 14 days (they stay in the Sheet). One date per person per story. Undo erases the tap from the log.
