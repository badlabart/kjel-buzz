# KJEL Buzz Report — "The Buzz"

Trello-style board of today's talkable stories for jocks and voicetrackers. Same look as the KJEL Event Board.
Three columns: National, Local, Music. About 10 cards each, most buzzworthy first. Cards under 12 hours old are gold.

## Open
Double-click `index.html`. No server needed.

## Refresh (daily, 6 AM)
1. `python3 -I scripts/collect.py` — pulls ~40 feeds and searches, drops downers, politics, gossip, spam and junk, ranks the rest, prints a shortlist.
2. Claude picks about 10 per column from the shortlist and writes `data/picks.json`.
3. `python3 -I scripts/build.py` — swaps Google News links for publisher links where Google allows, writes `data/buzz.js`, `index.html`, `docs/index.html`.

## Picking rules (step 2)
- Listener: working couple, 28–44, Lebanon area. Funny, weird, wholesome, or uplifting only.
- Never: tragedy, crime, illness, politics, celebrity gossip, outrage, ads, shopping lists.
- Never dated events or activities. Those belong on the Event Board.
- Local: Lebanon cards only when real (goal 30%). Then the 7 counties and the lake. Wider Ozarks only to fill.
- Music: country artists, songs, tours, chart news. Prefer artists on the Billboard Hot Country chart.
- Line: under 12 words, facts from the headline or summary only. Blank when it would repeat the headline.

## Buzz signals (the "BUZZ:" line)
Google searches today (Google Trends) · outlets carrying the same story · Wikipedia reads yesterday · Billboard Hot Country rank.
These stand in for virality. Facebook, TikTok, Instagram, X and Reddit share counts are not available.

## Sources
- National: Google News searches (viral, heartwarming, weird, animals, records, lottery, Chiefs/Cards/Mizzou, season), Google Trends, Wikipedia, UPI Odd News, Good News Network, Upworthy, Fox News Lifestyle.
- Local: Google News searches for Lebanon, Laclede, Camden, Pulaski, Webster, Dallas, Wright, Miller, the lake, Springfield, Branson; Laclede County Record; My Ozarks Online; City of Lebanon; Downtown Lebanon; KY3; OzarksFirst.
- Music: Taste of Country, The Boot, Whiskey Riff, Saving Country Music, Billboard, Rolling Stone, Country Now, Google News; Billboard Hot Country chart.

## Known limits
- Google throttles the link lookup after heavy use. Unresolved cards keep a Google News link, which still opens the story in a modern browser.
- Feeds rarely carry feel-good Lebanon stories. The Local header shows "short today" when Lebanon is under 30%.
