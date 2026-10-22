# WireReady (News app, far-left column)

Boss 2026-10-22. The three news people (B, J, R) paste wire stories into the column, tap their letter when they use a
story, and the tap date shows under the story. Every tap is logged by date in a private Google Sheet, and the log is
emailed weekly. The column stays OFF the live page until `wireready/config.json` exists.

## What lives where
- `Code.gs` + `appsscript.json`: Google Apps Script web app (kept in the Google Sheet's script project).
- Private Google Sheet, two tabs: `Stories` (every pasted story) and `Taps` (the log: tapped date, who, story added, story text, story id).
- `scripts/page.py` (WR_* constants) draws the column; `scripts/build.py` `wireready_column()` adds it when `config.json` has a url.
- Stories and the report address are NEVER in this repo (it is public). They live in the Sheet and in Script properties.

## Setup (once, signed in to the Google account that should send the email)
1. sheets.google.com: new blank spreadsheet named WireReady.
2. Extensions > Apps Script. Replace Code.gs with `Code.gs` here. Project Settings > Show appsscript.json, paste `appsscript.json`.
3. Project Settings > Script properties: add `PASSCODE` (the shared passcode) and `REPORT_TO` (who gets the weekly email).
4. Run `setup` (Google asks for permission once), then run `installWeeklyTrigger`.
5. Deploy > New deployment > Web app. Execute as: Me. Who has access: Anyone. Copy the Web app URL.
6. Save it as `wireready/config.json`: `{"url": "https://script.google.com/macros/s/.../exec"}`, run `python3 -I scripts/build.py`, push.
7. Test: run `weeklyLog` from the editor; the email should arrive. Open the News page, enter the passcode once per browser.

## Behavior (Boss's spec in bold, the rest is Claude's reading)
- **Add Story** button opens a window; **Submit** puts the story at the top, just under the button, with a tiny "added Oct 22" before the first word.
- **B, J, R** letters on each story's first line. Tap = lit, tap again = undo (the tap is removed from the log too).
- **Tap date** shows under the story in tiny type ("B 10/22 · R 10/23"). Date only, Central time.
- **Log** = the `Taps` tab, one row per tap, in date order.
- **Weekly email**: Mondays about 6 AM Central, taps from the Monday-to-Sunday that just ended, grouped by day, full story text. A week with no taps still sends a one-line email.
- Stories drop off the page after 14 days (they stay in the Sheet). One date per person per story.
- Passcode is shared and asked once per browser. Anyone with it can tap any letter.
