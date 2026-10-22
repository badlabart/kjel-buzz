# WireReady (News app, far-left column + full page)

Boss 2026-10-22. LIVE: https://badlabart.github.io/kjel-news/ (column) and https://badlabart.github.io/kjel-news/wireready/ (full page).

## What it is
- Column on News: small "Full page" button, "+ Add Story", passcode box, newest 20 stories, "+N more" link.
- Full page: MOnet (imported daily from Missourinet), Bruce, Jeff, Riley (stories B, J and R entered). Columns scroll on their own.
- Add Story: the person checks B, J or R (required), pastes the story, Submit. It lands on top with a tiny "added Oct 22".
- B / J / R letters on every story: tap = used (tiny date shows under the story), tap again = undo.
- Every tap is logged by date in the Google Sheet (`Taps` tab) and emailed weekly.

## What lives where
- `Code.gs`: Google Apps Script web app inside the private Google Sheet "WireReady" (Boss's Google account). `appsscript.json` is reference only.
- Sheet tabs: `Stories` (id, added, text, by, link), `Taps` (tapped, who, story added, story text, story id, story from).
- `config.json`: the deployed web app address (public; the passcode guards the data). Delete it to switch WireReady off.
- `scripts/page.py` (WR_* constants) draws both pages; `scripts/build.py` (`wireready_column`, `wireready_full`) adds them.
- NEVER in this repo (it is public): stories, the passcode, the weekly email address. They live in the Sheet and in Script properties.

## Schedules (Apps Script triggers, run on Google's servers, not the Mac)
- Daily about 4 AM Central: `importMonet` adds new stories from https://www.missourinet.com/feed/ (headline + ~50-word excerpt + link). The feed is 20 items. The site's firewall refuses the default script agent, so the script asks like a browser. Full article text is NOT fetched: the site rate-limits rapid requests and its robots.txt asks for 30 seconds between them.
- Monday about 6 AM Central: `weeklyLog` emails the Monday-to-Sunday that just ended (taps grouped by day, full story text). A week with no taps still sends a one-line email.

## Menu in the Sheet (WireReady menu)
Set passcode, Set weekly email address, Import Missourinet stories now, Send last week's log now.

## Changing the script
1. Edit `Code.gs` here, run the node tests, push.
2. In the Sheet: Extensions > Apps Script, paste the new Code.gs, save.
3. Deploy > Manage deployments > edit (pencil) > Version: New version > Deploy. The web app address stays the same.
4. Run `selfTest` from the editor: it must log SELF TEST PASSED.

## Gotchas learned
- Sheets turns text starting with "=" into a formula even in a text-formatted cell; every cell is written with a leading apostrophe (`appendText_`). The real-Google `selfTest` caught it; the mock could not.
- A POST with Content-Type text/plain avoids the CORS preflight, so the page can call the script from github.io (verified live with a wrong passcode).
- Stories drop off the page after 14 days (they stay in the Sheet). One date per person per story. Undo erases the tap from the log.
