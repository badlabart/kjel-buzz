# KJEL Buzz Report — "The Buzz"

Trello-style board of today's talkable stories for jocks and voicetrackers. Same look as the KJEL Event Board.
Four columns: National (~10), Local (~20), Music (~10), Humor (~10), best first. Cards under 12 hours old are gold.
Each news card is ONE on-air sentence with full context, city in parentheses. Lebanon cities are highlighted.
Music has a search box (artist or song) at the top.

## Open
Double-click `index.html`. No server needed.

## Refresh (daily, 6 AM)
1. `python3 -I scripts/collect.py` — pulls ~45 feeds and searches plus one Reddit joke pull, drops downers, politics, gossip, spam and junk, ranks the rest, prints a shortlist. Also updates the music archive.
2. Claude picks about 10 per column from the shortlist and writes `data/picks.json`.
3. `python3 -I scripts/build.py` — swaps Google News links for publisher links where Google allows, writes `data/buzz.js`, `index.html`, `docs/index.html`, `music_search.js`, and records which jokes ran.

## Music search
- KEPT forever: any music story naming an artist or quoting a song in the Billboard Country Airplay top 40 that day (`data/music_archive.json`). Tagged TOP 40.
- Everything else: searchable only until the next refresh replaces it (`data/music_recent.json`).
- Search shows stories kept off the board too (tagged NOT ON BOARD), so jocks see bad news before mentioning an artist.
- The archive loads only when someone searches, so the board stays fast on the old studio PC.

## Picking rules (step 2)
- Listener: working couple, 28–44, Lebanon area. Funny, weird, wholesome, or uplifting only.
- Never: tragedy, crime, illness, politics, celebrity gossip, outrage, ads, shopping lists.
- Never dated events or activities. Those belong on the Event Board.
- Local: about 20. Lebanon cards only when real (goal 30%; Lebanon stories stay eligible 14 days, others 7). Then the 7 counties and the lake, including high school wins and honors. Wider Ozarks only to fill.
- Music: country artists, songs, tours, chart news. Prefer artists in the Country Airplay top 40.
- Line: one on-air sentence, 15-35 words, full context, facts from the headline or summary only. Skip the story if the facts are too thin.
- City: the town from the source, shown in parentheses. Local always has one (county name if no town).
- Humor: about 6 jokes + 3-4 funniest-posts roundup links. Clean for broadcast, tellable aloud in under 20 seconds, lands by ear. No old classics.

## Humor freshness guards
- Jokes come from this week's 100 top-voted posts on r/dadjokes, r/cleanjokes, r/oneliners, r/Jokes (one combined pull; Reddit blocks a second).
- Auto-dropped: over 280 characters, dirty words, downers/politics, anything close to the 744 classic dad jokes in `data/classic_jokes.json`, anything already shown (`data/humor_shown.json`).

## Buzz signals (the "BUZZ:" line)
Google searches today (Google Trends) · outlets carrying the same story · Wikipedia reads yesterday · Country Airplay rank.
These stand in for virality. Facebook, TikTok, Instagram, X and Reddit share counts are not available.

## Sources
- National: Google News searches (viral, heartwarming, weird, animals, records, lottery, Chiefs/Cards/Mizzou, season), Google Trends, Wikipedia, UPI Odd News, Good News Network, Upworthy, Fox News Lifestyle.
- Local: 33 Google News searches (Lebanon, every town in the 7 counties, school teams, good-news themes, the lake, Springfield, Branson); Laclede County Record; My Ozarks Online; City of Lebanon; Downtown Lebanon; KY3; OzarksFirst; KSPR; KRMS.
- Music: Taste of Country, The Boot, Whiskey Riff, Saving Country Music, Billboard, Rolling Stone, Country Now, Google News; Billboard Country Airplay chart.
- Humor: Reddit joke boards; HuffPost comedy, Pleated Jeans, Cheezburger, Google News "funniest tweets/posts".

## Known limits
- Google throttles the link lookup after heavy use (the morning searches use most of the allowance). Lookups are spaced out and cached, so stories missed today usually resolve the next morning. Unresolved cards keep a Google News link, which still opens the story in a modern browser.
- Feeds rarely carry feel-good Lebanon stories. The Local header shows "short today" when Lebanon is under 30%.
