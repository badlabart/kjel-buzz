# KJEL Buzz Report — "The Buzz" + "News"

Trello-style board of today's talkable stories for jocks and voicetrackers. Same look as the KJEL Event Board.
Two apps from one build:
- The Buzz (docs/index.html): National (~10), LOCAL PRIDE (up to 24), Music (concerts + ~30 news), Nat'l Day (national days for today and the next 6 days).
- News (docs/news/index.html; published copy at https://badlabart.github.io/kjel-news/, repo KJEL-news), in Boss's order: The Johnsons, LOCAL PRIDE, Ozarks (up to 24; the old "Local"), Light, Morning News Only (20+). LOCAL PRIDE and The Johnsons also stay on the Buzz and Show Prep.
- WireReady (News app, far-left column; built 2026-10-22, OFF until wireready/config.json exists): the news people paste wire stories and tap B, J or R; tap dates show under each story; a private Google Sheet keeps the log and emails it weekly. Setup and behavior: wireready/README.md.
- Light (News app): uplifting, encouraging, amusing or funny stories from anywhere in the listening area, no Lebanon percentage, no card limit. `python3 -I scripts/light.py` writes data/light_pool.json; Claude writes data/picks_light.json; build.py adds the column. A story LOCAL PRIDE, National or Morning News Only carries stays there; Light wins over Ozarks.
- Show Prep (docs/show-prep/index.html, https://badlabart.github.io/kjel-buzz/show-prep/): Wx, LOCAL PRIDE, Nat'l Day, Music, Timely, The Johnsons, then the KJEL Event Board columns except KIM ONLY and Live Music (read from ~/Documents/Claude/Projects/KJEL-event-board/data/events.js, upcoming only), then National at the far right.
No card in any app should need a click to understand. Cards under 12 hours old are gold.
Each news card is ONE on-air sentence with full context, city in parentheses. Lebanon cities are highlighted.
Music has a search box (artist or song) at the top.

## Open
Double-click `index.html`. No server needed.

## Refresh (daily, 6 AM)
1. `python3 -I scripts/collect.py` — pulls ~45 feeds and searches plus one Reddit joke pull, drops downers, politics, gossip, spam and junk, ranks the rest, prints a shortlist. Also updates the music archive.
2. Claude picks about 10 per column from the shortlist and writes `data/picks.json`.
3. `python3 -I scripts/build.py` — swaps Google News links for publisher links where Google allows, writes `data/buzz.js`, `index.html`, `docs/index.html`, `music_search.js`, and records which jokes ran.

## Music column
- Concert cards (top): Country Airplay top-40 artists playing Camdenton, Osage Beach, Springfield or Branson first, then Kansas City and St. Louis. Found on AllEvents city pages (each page shows only its first ~10 events, so some shows are missed). Saved in `data/concerts.json`; each stays until the show date passes. The card names the whole bill.
- News cards: kept in `data/music_board.json` up to 30 days, about 30 at a time. Each morning adds 5-15 new ones; `music_drop` in picks.json replaces an older card with a better or more local one.
- Top-40 artist stories tied to our area (tour stops, sightings, local ties) are searched 30 days back and tagged NEAR US or KC/STL.

## Music search
- KEPT forever: any music story naming an artist or quoting a song in the Billboard Country Airplay top 40 that day (`data/music_archive.json`). Tagged TOP 40.
- Everything else: searchable only until the next refresh replaces it (`data/music_recent.json`).
- Search shows stories kept off the board too (tagged NOT ON BOARD), so jocks see bad news before mentioning an artist.
- The archive loads only when someone searches, so the board stays fast on the old studio PC.

## Picking rules (step 2)
- Listener: working couple, 28–44, Lebanon area. Funny, weird, wholesome, or uplifting only.
- Never: tragedy, crime, illness, politics, celebrity gossip, outrage, ads, shopping lists.
- Never dated events or activities. Those belong on the Event Board.
- Local: up to 24, CONGRATULATIONS first (awards, honors, scholarships, school heroes, team wins, business anniversaries, ribbon cuttings) with a CONGRATS tag. Split 50/50: up to 12 Lebanon + up to 12 from the rest of the core area (the 7 counties and the Lake). No Springfield or Branson. Lebanon is never padded; the header shows the real split.
- Freshness: Lebanon congrats 21 days, core-area congrats 14, other Lebanon 14, other core-area 7.
- Music: country artists, songs, tours, chart news. Prefer artists in the Country Airplay top 40.
- Line: one on-air sentence, 15-35 words, full context, facts from the headline or summary only. Skip the story if the facts are too thin.
- Never a teaser: the line states the finding or result. Teaser headlines get their article text printed in the shortlist so the finding can be written in.
- City: the town from the source, shown in parentheses. Local always has one (county name if no town).
- LOCAL PRIDE: awards and career milestones, the bigger the better (a national or state award outranks a local one). Never congratulate anyone for passing an inspection or other routine compliance (inspections, audits, license renewals, code checks); Boss, 2026-10-23: "we don't congratulate people for passing an inspection." collect.py does not tag such stories CONGRATS?. Accomplishments only. Format: LABEL ("World Food Champs", "New Coach") – names, from place, what they earned, when and where. Never "Congratulations to". No names in the source = no card. Article text is read so names don't need a click.
- Local: useful, interesting local news and local pride that isn't an award. Nothing that's a downer.
- Both local columns: up to 12 Lebanon + up to 12 other towns. Other towns HIGH first (Waynesville, St. Robert, Fort Leonard Wood, Bolivar, Marshfield, Osage Beach, Eldon, Camdenton), then LOW (Richland, Buffalo, Sunrise Beach, Four Seasons, Lake Ozark, Laurie, Crocker, Hermitage, Fair Grove, Dixon, Pleasant Hope), then other core-area towns.
- Humor: radio show-prep bits in one line, no click: TODAY IS (quirky national days for today AND the next 6 days, each card showing its weekday, so jocks can voice track a week ahead; true story behind the day + funny take), VIRAL (trending story + sarcastic take), SATIRE ("From The Onion:"), ONE-LINER (fresh jokes, Showerthoughts). The funny takes are written by Claude each morning; the facts come from the source. Never tweets, posts or roundup links.

## Morning News Only
- Bizarre, stunning, weird, crazy stories a listener can't wait to share at work. Never negative; a harmless brush with the law is OK.
- Priority: listening area (eligible 14 days), then Missouri, then US (48 hours). International only when 10+ US outlets carry it or it is in Google Trends.
- Sources: UPI Odd News, NY Post Weird But True, Neatorama, Laughing Squid, the Mirror and Daily Star (international, rule above), and 13 targeted Google News searches (loose animals, odd finds, oddball records, Florida man, viral animals, Missouri and listening-area oddities).

## Humor freshness guards
- Jokes come from the last 24 hours' 100 top-voted posts on r/dadjokes, r/cleanjokes, r/oneliners, r/Jokes, r/Showerthoughts (one combined pull; Reddit blocks a second).
- Auto-dropped: over 170 characters (Humor must read in one line).
- Auto-dropped: over 280 characters, dirty words, downers/politics, anything close to the 744 classic dad jokes in `data/classic_jokes.json`, anything already shown (`data/humor_shown.json`).

## Buzz signals (the "BUZZ:" line)
Google searches today (Google Trends) · outlets carrying the same story · Wikipedia reads yesterday · Country Airplay rank.
These stand in for virality. Facebook, TikTok, Instagram, X and Reddit share counts are not available.

## Sources
- National: Google News searches (viral, heartwarming, weird, animals, records, lottery, Chiefs/Cards/Mizzou, season), Google Trends, Wikipedia, UPI Odd News, Good News Network, Upworthy, Fox News Lifestyle.
- Community congratulations: school live feeds for Waynesville, Gasconade C-4, Crocker, Fordland, School of the Osage, Iberia; news boards for Lebanon R-3 and Seymour; Richland schools RSS; Camdenton, Lake West, Mountain Grove chambers; Laclede Electric; Mercy Hospital Lebanon.
- Local feeds also: LakeExpo, Bolivar Herald-Free Press, Marshfield Mail, Buffalo Reflex.
- Local: ~45 Google News searches (Lebanon, every town in the 7 counties, school teams, honors/scholarships/business milestones, the lake); Lebanon R-3 Schools news page (no dates on the site, so a post is dated the day it is first seen and shows SCHOOL NEWS); Laclede County Record; My Ozarks Online; City of Lebanon; Downtown Lebanon; KY3; OzarksFirst; KSPR; KRMS.
- Music: Taste of Country, The Boot, Whiskey Riff, Saving Country Music, Billboard, Rolling Stone, Country Now, Google News; Billboard Country Airplay chart.
- Humor: Checkiday date pages (next 7 days, with each day's back story, cached in data/day_stories.json) and National Day Calendar (today), Daily Dot and Know Your Meme (viral), The Onion (satire), Reddit joke boards + Showerthoughts (one pull a day).

## Known limits
- Google throttles the link lookup after heavy use (the morning searches use most of the allowance). Lookups are spaced out and cached, so stories missed today usually resolve the next morning. Unresolved cards keep a Google News link, which still opens the story in a modern browser.
- Feeds carry few Lebanon congratulations; most live on Facebook (school, chamber, sports pages), which cannot be read automatically. The Local header shows "short today" when Lebanon is under 50%.

## Timely and The Johnsons (Show Prep only, Boss 2026-10-21)
`python3 -I scripts/extra.py` pulls candidates into `data/extra_pool.json` and prints a shortlist: IanGardner.com daily prep sheet, AAA gas, MDC season dates and calendar countdowns (Timely; no weather, the Wx column has it, Boss 2026-10-27); kid-safety recalls, parenting, cooking, MDC news, hunting and fishing, money feeds and one Reddit pull (The Johnsons). Claude writes `data/picks_extra.json` (ids, labels, lines; a Timely pick may set its own "date"); `build.py` adds both columns after Music. Johnsons never repeat (`data/extra_shown.json`, 60 days).

## Show Prep: day / date search and Wx (Boss, 2026-10-21)
- Search bar at the top of Show Prep only. "Search by:" has three choices (Boss, 2026-10-23, after the two-button version confused her): the choice sets what the box means and a line under the box says in plain words what it will do. Search runs it, and clicking a choice with text already typed runs it too (Boss, 2026-10-23: she typed a date, clicked One day, and expected results).
  - Word: cards holding EVERY word typed, in any order, anywhere in the card text (link labels like "Read story" do not count). A match inside a longer word counts ("ball" finds "football"). The Music box still searches the music archive.
  - One day: only cards dated that day (events, concerts, Timely, Nat'l Day); undated news cards hide until Clear.
  - From a day on (for voice tracking days ahead): every undated card stays, dated cards BEFORE the day hide; a column left empty hides too, and the note says how many earlier cards are hidden.
  - Day names ("Friday", "Fri") mean that day this week, Monday through Sunday; one already passed says so and offers a one-click link to next week's date. A date ("10/24", "Oct 24", "2026-10-24") without a year means its next occurrence. "today" and "tomorrow" work too.
  - Code: DAY_FORM / DAY_JS in scripts/page.py.
- Show Prep column order (Boss, 2026-10-23): Wx, LOCAL PRIDE, Nat'l Day, Music, Timely, The Johnsons, the Event Board columns, then National at the far right (SHOW_PREP_LAST in build.py). The Buzz keeps its own order.
- LOCAL PRIDE highlights its city wherever the line names it (Lebanon gold, other towns navy), on every page that shows LOCAL PRIDE.
- Holiday Events (Show Prep) runs in date and time order (Boss, 2026-10-27, replacing the 10-23 by-city grouping), each card led by its city name in color: Lebanon always the station gold, every other town one fixed color (CITY_COLORS in page.py; unlisted towns get a color from their name). Other Event Board columns have no city name. Turned on by "city_tags" in build.py event_columns(); event cards carry data-min for the time order.
- Wx is the first column (scripts/wx.py, National Weather Service, no key). Rule (Boss): a short general forecast for the whole area by day, then ONLY severe weather.
- General weather (Boss, 2026-10-27: a short forecast for every day of the week, each with its date, and the card says what area it is for): an AREA FORECAST card headed "Marshfield to Lake of the Ozarks", one line per day for 7 days ("TUE 10/27 Partly sunny to mostly cloudy, highs 73-76."; the page adds TODAY / TOMORROW and drops days gone by). A wet day adds who gets rain and when ("Waynesville 70% rain afternoon", or "Entire area 60% storms all day"); a dry day says nothing about rain. Highs show on a day-ahead line and on a morning build; after 5 PM today reads "tonight". One NWS hourly-forecast point per county (Lebanon, Waynesville, Lake of the Ozarks [read at Osage Beach], Eldon, Bolivar, Marshfield, Buffalo, Hermitage, Hartville); a footer lists the places it was read at. Rain is named at 30% or more. Built at refresh time, not live. Today's Timely column carries no weather.
- Severe weather: only watches and warnings (no advisories or statements), one line each naming the counties and the cities in them: "FLOOD WATCH: Camden county (Camdenton, Osage Beach, Lake Ozark); Laclede county (Lebanon) until 7 PM (Thu 10/22)", warnings first, with an NWS details link. Nine counties: Laclede, Pulaski, Camden, Miller, Polk, Webster, Dallas, Hickory, Wright. Matching is by county, so a warning for part of a county lists the whole county. No watches or warnings shows "No watches or warnings."
- The build writes an alert snapshot; the page re-reads alerts live from api.weather.gov on load and every 5 minutes (WX_JS). If the live read fails it keeps the snapshot and the stamp stays "Alerts as of ...".

## Nat'l Day column (Boss, 2026-10-21)
Formerly Humor. National days only, today through 6 days ahead. Card: WEEKDAY 10/22 (TODAY/TOMORROW flag after it), the day's exact title in bold red ("National Bubble Blowing Day", never shortened; Boss, 2026-10-21), then one plain sentence: the most entertaining true fact about the day from its Checkiday story (default: why it was created). Dated facts give the year only.
