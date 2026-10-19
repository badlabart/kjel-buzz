# KJEL Buzz Report — "The Buzz"

Trello-style board of today's talkable stories for jocks and voicetrackers. Same look as the KJEL Event Board.
Five columns: National (~10), Local (up to 24), Music (~10), Humor (~10), Morning News Only (20+), best first. Cards under 12 hours old are gold.
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
- City: the town from the source, shown in parentheses. Local always has one (county name if no town).
- Humor: about 6 jokes + 3-4 funniest-posts roundup links. Clean for broadcast, tellable aloud in under 20 seconds, lands by ear. No old classics.

## Morning News Only
- Bizarre, stunning, weird, crazy stories a listener can't wait to share at work. Never negative; a harmless brush with the law is OK.
- Priority: listening area (eligible 14 days), then Missouri, then US (48 hours). International only when 10+ US outlets carry it or it is in Google Trends.
- Sources: UPI Odd News, NY Post Weird But True, Neatorama, Laughing Squid, the Mirror and Daily Star (international, rule above), and 13 targeted Google News searches (loose animals, odd finds, oddball records, Florida man, viral animals, Missouri and listening-area oddities).

## Humor freshness guards
- Jokes come from this week's 100 top-voted posts on r/dadjokes, r/cleanjokes, r/oneliners, r/Jokes (one combined pull; Reddit blocks a second).
- Auto-dropped: over 280 characters, dirty words, downers/politics, anything close to the 744 classic dad jokes in `data/classic_jokes.json`, anything already shown (`data/humor_shown.json`).

## Buzz signals (the "BUZZ:" line)
Google searches today (Google Trends) · outlets carrying the same story · Wikipedia reads yesterday · Country Airplay rank.
These stand in for virality. Facebook, TikTok, Instagram, X and Reddit share counts are not available.

## Sources
- National: Google News searches (viral, heartwarming, weird, animals, records, lottery, Chiefs/Cards/Mizzou, season), Google Trends, Wikipedia, UPI Odd News, Good News Network, Upworthy, Fox News Lifestyle.
- Community congratulations: school live feeds for Waynesville, Gasconade C-4, Crocker, Fordland, School of the Osage, Iberia; news boards for Lebanon R-3 and Seymour; Richland schools RSS; Camdenton, Lake West, Mountain Grove chambers; Laclede Electric; Mercy Hospital Lebanon.
- Local: ~40 Google News searches (Lebanon, every town in the 7 counties, school teams, honors/scholarships/business milestones, the lake); Lebanon R-3 Schools news page (no dates on the site, so a post is dated the day it is first seen and shows SCHOOL NEWS); Laclede County Record; My Ozarks Online; City of Lebanon; Downtown Lebanon; KY3; OzarksFirst; KSPR; KRMS.
- Music: Taste of Country, The Boot, Whiskey Riff, Saving Country Music, Billboard, Rolling Stone, Country Now, Google News; Billboard Country Airplay chart.
- Humor: Reddit joke boards; HuffPost comedy, Pleated Jeans, Cheezburger, Google News "funniest tweets/posts".

## Known limits
- Google throttles the link lookup after heavy use (the morning searches use most of the allowance). Lookups are spaced out and cached, so stories missed today usually resolve the next morning. Unresolved cards keep a Google News link, which still opens the story in a modern browser.
- Feeds carry few Lebanon congratulations; most live on Facebook (school, chamber, sports pages), which cannot be read automatically. The Local header shows "short today" when Lebanon is under 50%.
