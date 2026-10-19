"""Collect buzz candidates for the KJEL Buzz Report -> data/pool.json, then print the shortlist.

Run: python3 -I scripts/collect.py
The shortlist is what Claude picks from. Nothing here writes the board; build.py does.
"""
import base64
import email.utils
import html
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import md5
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "url_cache.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
NOW = datetime.now(timezone.utc)
CT = ZoneInfo("America/Chicago")
FRESH_HOURS = {"national": 48, "music": 48, "local": 24 * 7, "weird": 24 * 14}
WEIRD_AWAY_HOURS = 48  # Morning News Only: listening-area stories may be 14 days old, everything else 48 hours
LEBANON_FRESH_HOURS = 24 * 14  # Lebanon stories are scarce, so they get two weeks
CONGRATS_FRESH_HOURS = {0: 24 * 21, 1: 24 * 14}  # congratulations stay sayable longer: Lebanon 3 weeks, core area 2
SHORT = {"national": 30, "music": 40, "local": 80, "weird": 80}
# Things a jock can congratulate a local person, team, school or business for.
CONGRATS = re.compile(
    r"\b(awards?|awarded|honou?r(s|ed|ee)?|named|recogni[sz]\w*|scholarships?|dean'?s list|president'?s list|"
    r"honor roll|eagle scout|of the (week|month|year)|champions?|championship|state (qualifier|champion|title|finals?)|"
    r"qualif\w*|all-(state|district|conference|region)|hall of fame|first place|1st place|place[sd]|medals?|"
    r"anniversar\w*|years in business|ribbon[- ]cutting|grand opening|opens|expands|milestone|retir\w*|"
    r"graduat\w*|promot\w*|selected|wins?|won|record|semifinalists?|finalists?|signs with|commits? to|"
    r"wall of honor|teacher of the year|outstanding|excellence|achiev\w*|celebrat\w*)\b", re.I)
PER_SOURCE = {"national": 3, "music": 4, "local": 10, "weird": 6}  # cap per outlet in the shortlist
FAILED = []


def get(url, data=None, headers=None, timeout=25):
    h = {"User-Agent": UA}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def text(s):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def gn(q, days):
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(f"{q} when:{days}d")
            + "&hl=en-US&gl=US&ceid=US:en")


# ---------------- sources ----------------
SEASON = {
    1: '"snow day" OR "New Year" OR "ice fishing"', 2: '"Valentine\'s" OR "Super Bowl" OR "Groundhog"',
    3: '"St. Patrick\'s" OR "March Madness" OR "spring break"', 4: 'Easter OR prom OR "turkey season"',
    5: 'graduation OR "Mother\'s Day" OR "Memorial Day"', 6: '"Father\'s Day" OR "summer vacation" OR fishing',
    7: '"Fourth of July" OR fireworks OR "county fair"', 8: '"back to school" OR "state fair"',
    9: 'tailgate OR "homecoming" OR "pumpkin spice"', 10: 'Halloween OR pumpkin OR costume OR "corn maze"',
    11: 'Thanksgiving OR "deer season" OR "Black Friday"', 12: 'Christmas OR "Christmas lights" OR Santa',
}
NATIONAL_Q = [
    '"goes viral" OR "went viral" OR "viral video"',
    'heartwarming OR "feel-good" OR "pays it forward" OR "random act of kindness"',
    '(dog OR cat OR puppy OR kitten OR horse OR goat OR cow) (rescued OR adorable OR viral OR reunited)',
    '"world record" OR "Guinness World Records"',
    '(lottery OR jackpot OR scratch-off) winner',
    '(Chiefs OR "St. Louis Cardinals" OR Mizzou OR "Kansas City Royals") (fans OR viral OR celebrate OR record)',
    SEASON[NOW.month],
]
NATIONAL_FEEDS = [
    ("UPI Odd News", "https://rss.upi.com/news/odd_news.rss"),
    ("Good News Network", "https://www.goodnewsnetwork.org/feed/"),
    ("Upworthy", "https://www.upworthy.com/feed"),
    ("Fox News Lifestyle", "https://moxie.foxnews.com/google-publisher/lifestyle.xml"),
]
LOCAL_Q = [
    # (query, days). Lebanon searches look back two weeks; everything else one.
    ('"Lebanon, Mo." OR "Lebanon, Missouri" OR "Lebanon, MO"', 14),
    ('"Laclede County"', 14),
    ('Lebanon Missouri "Route 66"', 14),
    ('"Lebanon R-3" OR "Lebanon Yellowjackets" OR "Bennett Spring"', 14),
    ('site:laclederecord.com', 14),
    ('site:myozarksonline.com', 14),
    ('Lebanon Missouri (opens OR "grand opening" OR restaurant OR celebrates OR honored OR award OR record OR champion OR wins)', 14),
    # Congratulations: people, teams, schools and businesses (Lebanon 3 weeks, core area 2)
    ('Lebanon Missouri ("dean\'s list" OR "honor roll" OR scholarship OR "Eagle Scout" OR "of the month" OR "of the year" '
     'OR "hall of fame" OR "all-state" OR "all-district" OR "all-conference" OR award OR honored OR recognized OR named)', 21),
    ('Lebanon Missouri ("ribbon cutting" OR anniversary OR "years in business" OR "grand opening" OR expands OR "new location" OR milestone)', 21),
    ('"Laclede County" (award OR honored OR scholarship OR champion OR "of the year" OR recognized OR anniversary)', 21),
    ('(Yellowjackets OR "Lebanon High School" OR "Lebanon R-3" OR "Lebanon R-III") (state OR district OR champions OR honors OR qualifies OR places OR signs)', 21),
    ('(Camdenton OR "Osage Beach" OR "Lake Ozark" OR "Sunrise Beach" OR Laurie OR "Linn Creek") '
     '(award OR honored OR scholarship OR "of the year" OR champion OR "Eagle Scout" OR anniversary OR "ribbon cutting")', 14),
    ('(Waynesville OR "St. Robert" OR "Fort Leonard Wood" OR Richland OR Dixon OR Crocker) '
     '(award OR honored OR scholarship OR "of the year" OR champion OR "Eagle Scout" OR anniversary OR "ribbon cutting")', 14),
    ('(Marshfield OR Seymour OR Rogersville OR Niangua OR Buffalo OR Louisburg) Missouri '
     '(award OR honored OR scholarship OR "of the year" OR champion OR "Eagle Scout" OR anniversary OR "ribbon cutting")', 14),
    ('("Mountain Grove" OR Hartville OR Mansfield OR Norwood OR Eldon OR Iberia OR Tuscumbia) Missouri '
     '(award OR honored OR scholarship OR "of the year" OR champion OR "Eagle Scout" OR anniversary OR "ribbon cutting")', 14),
    ('(Conway OR Phillipsburg OR Stoutland OR Falcon OR Eldridge) Missouri', 7),
    ('(Richland OR Dixon OR Crocker OR Laquey) Missouri', 7),
    ('"Sunrise Beach" OR Laurie OR "Linn Creek" OR "Climax Springs" OR "Macks Creek" OR "Gravois Mills"', 7),
    ('(Seymour OR Rogersville OR Fordland OR Niangua) Missouri', 7),
    ('(Louisburg OR Urbana OR "Long Lane") Missouri', 7),
    ('(Hartville OR Mansfield OR Norwood) Missouri', 7),
    ('(Tuscumbia OR Brumley OR "St. Elizabeth") Missouri', 7),
    ('(Camdenton OR Waynesville OR Marshfield OR Buffalo OR "Mountain Grove" OR Eldon OR Richland OR Conway OR Hartville OR Iberia OR Seymour OR Dixon) '
     '(win OR wins OR champions OR district OR state OR undefeated OR honored)', 7),
    ('Ozarks Missouri (opens OR "grand opening" OR "new restaurant" OR celebrates OR honored OR award OR "first ever")', 7),
    ('"Lake of the Ozarks" (celebrates OR record OR opens OR new OR honored OR rescued)', 7),
    ('"Lake of the Ozarks" OR "Osage Beach" OR Camdenton OR "Lake Ozark"', 7),
    ('"Camden County" Missouri', 7),
    ('"Pulaski County" Missouri OR "Fort Leonard Wood" OR Waynesville OR "St. Robert"', 7),
    ('"Bolivar, Mo." OR "Bolivar, Missouri" OR "Polk County" Missouri OR "Pleasant Hope" OR "Fair Grove, Mo."', 7),
    ('Hermitage Missouri OR "Hickory County" Missouri OR "Four Seasons" Missouri OR "Lake Ozark"', 7),
    ('(Bolivar OR "Pleasant Hope" OR "Fair Grove" OR Hermitage) Missouri '
     '(award OR honored OR scholarship OR "of the year" OR champion OR "Eagle Scout" OR anniversary OR "ribbon cutting")', 14),
    ('"Webster County" Missouri OR "Marshfield, Mo." OR "Seymour, Mo."', 7),
    ('"Dallas County" Missouri OR "Buffalo, Mo."', 7),
    ('"Wright County" Missouri OR "Mountain Grove" OR "Hartville, Mo." OR "Mansfield, Mo."', 7),
    ('"Miller County" Missouri OR "Eldon, Mo." OR "Iberia, Mo."', 7),
    ('site:lakeexpo.com', 7),
    ('site:krmsradio.com', 7),
    ('Ozarks (heartwarming OR viral OR "first ever" OR record OR rescued OR celebrates OR surprise)', 7),
]
LOCAL_FEEDS = [
    ("My Ozarks Online", "https://www.myozarksonline.com/feed/"),
    ("City of Lebanon", "https://www.lebanonmissouri.org/RSSFeed.aspx?ModID=1&CID=All-newsflash.xml"),
    ("Downtown Lebanon", "https://www.downtownlebanonmo.com/feed/"),
    ("KY3", "https://www.ky3.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("OzarksFirst", "https://www.ozarksfirst.com/feed/"),
    ("OzarksFirst", "https://www.ozarksfirst.com/news/local-news/feed/"),
    ("KSPR", "https://www.kspr.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("KRMS", "https://www.krmsradio.com/feed/"),
    ("LakeExpo.com", "https://www.lakeexpo.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc"),
    ("Bolivar Herald-Free Press", "https://www.bolivarmonews.com/feed/"),
    ("Marshfield Mail", "https://www.marshfieldmail.com/feed/"),
    ("Buffalo Reflex", "https://www.buffaloreflex.com/feed/"),
]
MUSIC_Q = ['"country music" OR "country singer" OR "country star"']
# Morning News Only: bizarre, stunning, weird, crazy, never negative. Listening area first, then US, then
# international only when US outlets are carrying it widely (10+) or it is in Google Trends.
WEIRD_Q = [
    ('"odd news" OR "weird news" OR "strange but true" OR bizarre OR baffled OR "mystery solved"', 1),
    ('(raccoon OR goat OR alligator OR bear OR moose OR emu OR llama OR kangaroo OR cow OR pig OR snake OR python) '
     '(loose OR escaped OR stuck OR wandered OR rescued OR spotted OR "on the run")', 2),
    ('(police OR deputies OR firefighters OR troopers) (raccoon OR goat OR alligator OR cow OR pig OR emu OR snake OR turkey OR duck)', 2),
    ('(found OR discovered OR unearthed) (treasure OR "time capsule" OR "message in a bottle" OR meteorite OR fossil OR shipwreck OR "hidden room")', 2),
    ('"Guinness World Records" OR "world record" (pumpkin OR dog OR cat OR tallest OR longest OR largest OR oldest OR fastest)', 2),
    ('"Florida man" OR "Florida woman"', 2),
    ('record (catfish OR bass OR buck OR deer OR pumpkin OR watermelon OR sunflower OR sturgeon OR paddlefish OR gar)', 3),
    ('(baffled OR stunned OR puzzled) (residents OR neighbors OR scientists OR homeowner OR police)', 2),
    ('"caught on camera" OR "caught on video" (dog OR cat OR bear OR deer OR raccoon OR goat OR cow OR squirrel)', 2),
    ('"goes viral" OR "went viral" (dog OR cat OR raccoon OR goat OR bear OR deer OR cow OR squirrel OR parrot)', 2),
    ('Missouri (bizarre OR strange OR unusual OR weird OR rare OR "world record" OR albino OR "state record" OR mystery OR escaped)', 7),
    ('(Lebanon OR Camdenton OR "Lake of the Ozarks" OR Waynesville OR Marshfield OR Buffalo OR "Mountain Grove" OR Eldon OR Laclede '
     'OR "Osage Beach" OR "Fort Leonard Wood") Missouri (unusual OR rare OR giant OR record OR strange OR albino OR mystery OR bizarre)', 14),
]
WEIRD_FEEDS = [
    ("UPI Odd News", "https://rss.upi.com/news/odd_news.rss"),
    ("New York Post", "https://nypost.com/weird-but-true/feed/"),
    ("Neatorama", "https://www.neatorama.com/feed/"),
    ("Laughing Squid", "https://laughingsquid.com/feed/"),
    ("The Mirror", "https://www.mirror.co.uk/news/weird-news/?service=rss"),
    ("Daily Star", "https://www.dailystar.co.uk/news/weird-news/?service=rss"),
]
WEIRD_SOURCES = {l for l, _ in WEIRD_FEEDS}
# Google News items must sound weird; business, sports and medical "giants" and "records" are noise.
WEIRD_WORDS = re.compile(
    r"bizarre|strange|weird|odd\b|unusual|myster\w*|baffl\w*|stunn\w*|rare\b|world record|guinness|record-breaking|"
    r"escaped|on the loose|loose\b|stuck\b|rescued|spotted|viral|hilarious|unbelievable|first-ever|unearthed|treasure|"
    r"time capsule|message in a bottle|meteorite|fossil|alligator|gator|raccoon|emu|goat|moose|llama|kangaroo|squirrel|"
    r"possum|opossum|python|snake|pumpkin|florida man|florida woman|albino|two-headed|lookalike|doppelg|dressed as|"
    r"record\b|sturgeon|paddlefish|catfish|caught on (camera|video)|puzzled|"
    r"giant (pumpkin|squid|fish|catfish|snake|jellyfish|tortoise|turtle|spider|crab|lobster|zucchini|potato|carrot)", re.I)
WEIRD_NOISE = re.compile(
    r"\b(stocks?|shares|investor\w*|earnings|ceo|acquir\w*|merger|oil|banking|packaging|nfl|nba|nhl|mlb|playoffs?|"
    r"quarterback|halftime|coach|season|vs\.?|game|innings?|touchdown|tgl|patients?|study|clinical|case report|"
    r"infection|bacteri\w*|startup|ipo|revenue|market|podcast|review|trailer|album|poll|nsfw|penis|porn|nude|naked|"
    r"legal limit|dui|dwi|drunk|inmate|manhunt|fugitive|anime|manga|jojo|bravo|soap|interview|reacts|episode|"
    r"series|emergency landing|black holes?|nasa|chart|airplay|billboard)\b", re.I)
INTL_SOURCES = {"The Mirror", "Daily Star"}
FOREIGN_PLACE = re.compile(
    r"\b(UK|U\.K\.|Britain|British|Brit|Brits|England|English|London|Scotland|Scottish|Wales|Welsh|Ireland|Irish|"
    r"Australia\w*|Aussie|New Zealand|Kiwi|Canada|Canadian|Quebec|Ontario|Mexico|Mexican|Brazil\w*|Argentin\w*|"
    r"Japan\w*|China|Chinese|Korea\w*|India\w*|Thailand|Thai|Vietnam\w*|Philippin\w*|Indonesia\w*|Germany|German|"
    r"France|French|Paris|Spain|Spanish|Italy|Italian|Rome|Netherlands|Dutch|Sweden|Swedish|Norway|Norwegian|"
    r"Finland|Finnish|Denmark|Danish|Poland|Polish|Russia\w*|Ukrain\w*|Turkey|Turkish|Croatia\w*|Greece|Greek|"
    r"Egypt\w*|Africa\w*|Nigeria\w*|Kenya\w*|Dubai|Saudi|Israel\w*|Singapore|Taiwan\w*|Bali|Peru|Chile|Colombia\w*|"
    r"Moldova\w*|Kyrgyz\w*|Bishkek|Macedonia\w*|Cornwall|Cheltenham|St Albans|Yorkshire|Mysuru|Odisha|Kerala|Mumbai|"
    r"Delhi|Bangalore|Pretoria|Cape Town|Johannesburg|Tokyo|Osaka|Gunma|Seoul|Beijing|Shanghai|Hong Kong|Sydney|"
    r"Melbourne|Toronto|Vancouver|Montreal|Dublin|Glasgow|Edinburgh|Manchester|Liverpool|Scots?|Britons|Surrey|"
    r"Donegal|Malaysia\w*|Thane|Isle of Wight|South Shields|Suffolk|Essex|Devon|Kent, England|Center Parcs)\b")
# A US state in the story keeps it US even when a foreign outlet carried it.
US_PLACE = re.compile(
    r"\b(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|"
    r"Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|"
    r"Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|"
    r"Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|"
    r"West Virginia|Wisconsin|Wyoming|U\.S\.|American)\b")
# Outlets that are clearly outside the US (or not in English) mark a story international.
FOREIGN_SOURCE = re.compile(
    r"india|gulf news|herts|gloucestershire|york press|joburg|mathrubhumi|newsx|bhaskar|samaa|\.in\b|japan times|"
    r"globe and mail|vietnam|kursiv|good things guy|futura|daily mail|mirror|daily star|the sun\b|express|bbc|guardian|"
    r"independent|telegraph|scotsman|irish|ireland|abc\.net\.au|\.com\.au|cbc|ctv|news24|dawn|khaleej|arab|straits|"
    r"south china|surrey|gb news|turkmen|mid-day|shields|suffolk|kent online|wales|yorkshire|manchester|"
    r"[^\x00-\x7f]", re.I)
# Weird news may involve a harmless brush with police; it may never involve death, injury, violence or victims.
WEIRD_BLOCK = re.compile(
    r"\b(murder\w*|homicide|kill(ed|s|ing)?|dead|dies|died|death|deaths|fatal\w*|shoot\w*|shot|stab\w*|gunman|"
    r"gunfire|abus\w*|assault\w*|rape\w*|molest\w*|sex\w*|overdose|drown\w*|suicide|missing|body found|remains|"
    r"obituar\w*|funeral|cancer|tragic|tragedy|grie(f|ving)|mourn\w*|victim\w*|kidnap\w*|trafficking|crash\w*|"
    r"wreck|collision|injur\w*|airlift\w*|hospitali[sz]ed|critical condition|explosion|measles|outbreak|tornado|"
    r"flood\w*|evacuat\w*|die|dying|arson\w*|blaze|burn(ed|s)? down|destroyed|prison|sentenc\w*|"
    r"bitten|mauled|attack\w*|bloody|gore|cannibal\w*|corpse|skeleton found|euthaniz\w*|starv\w*)\b", re.I)

MUSIC_FEEDS = [
    ("Taste of Country", "https://tasteofcountry.com/feed/"),
    ("The Boot", "https://theboot.com/feed/"),
    ("Whiskey Riff", "https://www.whiskeyriff.com/feed/"),
    ("Saving Country Music", "https://www.savingcountrymusic.com/feed"),
    ("Billboard", "https://www.billboard.com/c/music/country/feed/"),
    ("Rolling Stone", "https://www.rollingstone.com/music/music-country/feed/"),
    ("Country Now", "https://countrynow.com/feed/"),
]

# Towns: tier 0 = Lebanon, 1 = the 7 counties + lake, 2 = wider Ozarks (filler only).
LEBANON = re.compile(r"\bLebanon\b|\bLaclede\b|Bennett Spring|Yellowjackets", re.I)
NOT_MO_LEBANON = re.compile(r"Lebanon,? (Ohio|OH|Pa\.?|Pennsylvania|Tenn\.?|Tennessee|TN|N\.?H\.?|New Hampshire|Ind\.?|Indiana|Ky\.?|Kentucky|Ore\.?|Oregon|Ill\.?|Illinois|Conn\.?|Va\.?|Virginia)(?![a-z])|\bBeirut\b|\bLebanese\b|Israel|Hezbollah|Lebanon Daily News|Lebanon Democrat|Lebanon Reporter|Lebanon Express|Lebanon Valley|Lebanon County", re.I)
LEBANON_SOURCES = {"Laclede County Record", "My Ozarks Online", "City of Lebanon", "Downtown Lebanon", "Lebanon R-3 Schools"}
# "KRMS" is a Lake radio station, so it is a local outlet but not a Lebanon one.
MO_MARK = re.compile(r"\b(Mo\.|MO|Missouri|Ozarks?)\b")
LOCAL_OUTLET = re.compile(
    r"laclede|ozark|ky3|kolr|kspr|lakeexpo|lake sun|lake news|news-leader|branson globe|reflex|webster county citizen|"
    r"marshfield mail|komu|krcg|kmzu|ksmu|krms|kttn|sgf|springfield daily|sedalia|daily guide|missouri|"
    r"myozarks|guidon|houston herald|eldon|kspr|krms|bolivar|polk county", re.I)
COUNTY_TOWNS = [
    "Conway", "Phillipsburg", "Stoutland", "Eldridge", "Brumley",
    "Waynesville", "St. Robert", "Saint Robert", "Fort Leonard Wood", "Dixon", "Crocker", "Richland", "Laquey", "Pulaski County",
    "Camdenton", "Osage Beach", "Linn Creek", "Sunrise Beach", "Climax Springs", "Macks Creek", "Lake Ozark", "Lake of the Ozarks", "Camden County", "Laurie", "Gravois Mills",
    "Marshfield", "Seymour", "Rogersville", "Fordland", "Niangua", "Webster County",
    "Buffalo", "Louisburg", "Urbana", "Dallas County",
    "Mountain Grove", "Hartville", "Mansfield", "Norwood", "Wright County",
    "Eldon", "Tuscumbia", "Iberia", "Miller County",
    "Bolivar", "Pleasant Hope", "Polk County", "Hermitage", "Hickory County", "Fair Grove",
    "Village of Four Seasons", "Four Seasons",
]
WIDER_TOWNS = ["Springfield", "Branson", "Rolla", "Nixa", "Ozark", "Republic", "West Plains", "Ozarks"]
# Boss's order for the non-Lebanon half of LOCAL PRIDE and Local (2026-10-19).
HIGH_TOWNS = {"Waynesville", "St. Robert", "Fort Leonard Wood", "Bolivar", "Marshfield", "Osage Beach", "Eldon", "Camdenton"}
LOW_TOWNS = {"Richland", "Buffalo", "Sunrise Beach", "Four Seasons", "Village of Four Seasons", "Lake Ozark", "Laurie",
             "Crocker", "Hermitage", "Fair Grove", "Dixon", "Pleasant Hope", "Lake"}


def town_priority(town, tier):
    """0 Lebanon, 1 high-priority town, 2 lower-priority town, 3 any other core-area town."""
    if tier == 0:
        return 0
    return 1 if town in HIGH_TOWNS else 2 if town in LOW_TOWNS else 3


def town_of(title, desc, source):
    blob = f"{title} {desc}"
    if not (source in LEBANON_SOURCES or LOCAL_OUTLET.search(source) or MO_MARK.search(blob)):
        return None, None
    if NOT_MO_LEBANON.search(source):
        return None, None
    if source in LEBANON_SOURCES and not NOT_MO_LEBANON.search(blob):
        m = re.search(r"\b(" + "|".join(map(re.escape, COUNTY_TOWNS)) + r")\b", title)
        if m and not LEBANON.search(title):
            return m.group(1), 1
        return "Lebanon", 0
    if LEBANON.search(blob) and not NOT_MO_LEBANON.search(blob):
        return "Lebanon", 0
    for t in COUNTY_TOWNS:
        if re.search(r"\b" + re.escape(t) + r"\b", blob, re.I):
            return t.replace("Saint Robert", "St. Robert").replace("Lake of the Ozarks", "Lake"), 1
    for t in WIDER_TOWNS:
        if re.search(r"\b" + re.escape(t) + r"\b", blob):
            return t, 2
    return None, None


# ---------------- filters ----------------
TRAGIC = re.compile(
    r"\b(murder\w*|homicide|kill(ed|s|ing)?|dead|dies|died|death|deaths|fatal\w*|shoot\w*|shot|stab\w*|gunman|"
    r"gunfire|arrest\w*|charged|charges|sentenc\w*|indict\w*|convicted|guilty|plead\w*|prison|jail\w*|inmate|"
    r"abus\w*|assault\w*|rape|molest\w*|overdose|drown\w*|suicide|missing|body found|remains|obituar\w*|funeral|"
    r"passed away|cancer|tragic|tragedy|grie(f|ving)|mourn\w*|victim\w*|suspect\w*|kidnap\w*|trafficking|crash\w*|"
    r"wreck|collision|injur\w*|airlift\w*|hospitali[sz]ed|critical condition|explosion|layoffs?|laid off|"
    r"bankrupt\w*|recall\w*|measles|outbreak|tornado|flood\w*|evacuat\w*|scam\w*|fraud|die|dying|arson\w*|"
    r"accused|fires|blaze|burn(ed|s)? down|unsafe|destroyed|engulf\w*|"
    r"fire(?! (department|dept|truck|station|chief|district|fighters?|protection|academy|prevention|safety|pit|up)))\b", re.I)
POLITICS = re.compile(
    r"\b(trump|biden|vance|harris|obama|democrat\w*|republican\w*|gop|congress\w*|senat\w*|legislat\w*|"
    r"lawmaker\w*|election\w*|ballot|voters?|voting|campaign\w*|candidate\w*|governor|kehoe|hawley|schmitt|"
    r"white house|administration|immigra\w*|deport\w*|tariff\w*|shutdown|supreme court|lawsuit|sue[sd]?|"
    r"court|judge|attorney general|protest\w*|israel|gaza|ukraine|russia|iran|press secretary|mamdani|noem|"
    r"kennedy center|amendment|proposition|ordinance|tax(es)?|council|commission\w*|data center|politic\w*|"
    r"midterms?)\b", re.I)
ICE = re.compile(r"\bICE\b")
GOSSIP = re.compile(
    r"\b(divorc\w*|split|splits|breakup|break up|cheat\w*|affair|feud\w*|slam\w*|blast\w*|rehab|dui|scandal|"
    r"spoiler\w*|backlash|controvers\w*|accus\w*|allegation\w*|threat\w*|harass\w*|meltdown|diss|outrage\w*)\b", re.I)
ENGLISH = re.compile(r"\b(the|a|an|to|of|in|and|for|is|on|with|at|from|his|her|after|this|how|why|what|new|gets|says)\b", re.I)
# Spam and non-US stories that ride Google News "viral" searches.
SPAM = re.compile(r"x{3}|xnxx|\bmms\b|\bleak(ed)?\b|uncut|[\U0001F300-\U0001FAFF]|\b(?=\w*\d)(?=\w*[a-z])(?=\w*[A-Z])\w{8,}\b", re.I)
FOREIGN = re.compile(
    r"\b(pakistan\w*|india\w*|bollywood|bigg boss|cricket|lakh|crore|rs\.? ?\d|premier league|nigeria\w*|"
    r"philippin\w*|kenya\w*|bangladesh\w*|duchess|royal family|prince \w+|king charles)\b", re.I)
JUNK = re.compile(
    r"(realtor\.com|zillow|apartments\.com|maxpreps|legacy\.com|holman-howe|funeral home|for sale|\bquiz\b|"
    r"live cams|products you|amazon|coupon|deals?\b|horoscope|crossword|wordle|connections hint|"
    r"winning numbers|lottery numbers|\bstocks?\b|nasdaq|s&p|dow jones|earnings|^opinion|announcements|"
    r"question of the week|e-edition|classifieds|public notice|trading post|archives|letters? to the editor|"
    r"^watch live|weather (alert|watch|warning)|forecast|results for|pick 3|cash pop|don't pay|full price|"
    r"tribute wall|schedule|^(monday|tuesday|wednesday|thursday|friday|saturday|sunday), \w+ \d|"
    r"maxpreps|sports illustrated|lyrics|sponsored)", re.I)
DOWNER = re.compile(
    r"\b(fire|fires|storm\w*|hospital|police|sheriff|deput\w*|warn\w*|closed|closing|closure|outage|unsafe|"
    r"delay\w*|shortage|debt|lawsuit|paychecks?|hot buses|concern\w*|worr\w*|danger\w*|risk)\b", re.I)
FUN = re.compile(
    r"\b(viral|hilarious|funny|adorable|heartwarming|wholesome|surpris\w*|record|first[- ]ever|rescued|reunit\w*|"
    r"celebrat\w*|wins?|winner|giant|biggest|pumpkin|halloween|costume|dog|puppy|cat|kitten|goat|horse|bear|"
    r"emu|fish\w*|trophy|champion\w*|propos\w*|wedding|birthday|anniversary|grand opening|opens|opening|"
    r"festival|parade|honou?rs?|award\w*|donat\w*|volunteer\w*|hero\w*|kindness|neon|route 66|duet|"
    r"no\. 1|number one|tour|new song|new album|surprise|sings?|cover)\b", re.I)


def blocked(col, title, desc, src=""):
    blob = f"{title} {desc[:200]}"
    if JUNK.search(f"{title} | {src}"):
        return "junk"
    if SPAM.search(title):
        return "spam"
    if col == "national" and FOREIGN.search(blob):
        return "non-US"
    if col in ("national", "weird") and not ENGLISH.search(title):
        return "not English"
    if col == "weird":
        if WEIRD_BLOCK.search(blob) or POLITICS.search(title) or ICE.search(title):
            return "downer/politics"
        if WEIRD_NOISE.search(title) or (src not in WEIRD_SOURCES and not WEIRD_WORDS.search(title)):
            return "not weird"
    elif TRAGIC.search(title) or POLITICS.search(title) or ICE.search(title):
        return "downer/politics"
    if col != "local" and GOSSIP.search(title):
        return "gossip"
    if col == "local" and re.fullmatch(r"[A-Z][\w.\"'()\- ]{2,40}", title) and len(title.split()) <= 4:
        return "obit-style title"
    if TRAGIC.search(blob) and col == "local":
        return "downer in summary"
    return None


# ---------------- parsing ----------------
def parse_feed(body, source, col, from_gn=False, days=None):
    body = body.lstrip()
    root = ET.fromstring(body)
    out = []
    for it in root.findall(".//item"):
        title = text((it.findtext("title") or ""))
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
        try:
            ts = email.utils.parsedate_to_datetime(pub)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            try:
                ts = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                continue
        ts = min(ts, NOW)  # some feeds post-date their items
        src = source
        desc = text(it.findtext("description") or "")
        if from_gn:
            s = it.find("source")
            src = (s.text or "").strip() if s is not None else "Google News"
            if title.endswith(" - " + src):
                title = title[: -len(src) - 3].strip()
            desc = ""  # Google News descriptions only repeat the headline
        out.append({"col": col, "title": title, "url": link, "source": src, "ts": ts, "desc": desc[:400],
                    "gn": from_gn, "query": days})
    return out


def pull(job):
    kind, col, label, url = job
    try:
        body = get(url)
        return parse_feed(body, label, col, from_gn=(kind == "gn"))
    except Exception as e:
        FAILED.append(f"{label} ({str(e)[:40]})")
        return []


def lebanon_r3():
    """Lebanon R-3 Schools news posts: staff honors, school awards, new facilities, coaches.
    The page lists posts newest first without dates, so each post is dated the day this script first saw it."""
    page = "https://www.lebanonr3.org/our-district/news-archive"
    try:
        b = get(page)
    except Exception as e:
        FAILED.append(f"Lebanon R-3 news ({str(e)[:40]})")
        return []
    path = DATA / "r3_seen.json"
    first_run = not path.exists()
    seen = json.loads(path.read_text()) if path.exists() else {}
    out = []
    posts = re.findall(r'class="fsPostLink" data-slug="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
    for n, (slug, title) in enumerate(posts):
        if slug not in seen:
            # First run: the 5 newest posts count as new; older ones are marked 60 days old.
            seen[slug] = (NOW if not first_run or n < 5 else NOW - timedelta(days=60)).isoformat()
        out.append({"col": "local", "title": text(title), "url": page, "source": "Lebanon R-3 Schools",
                    "ts": datetime.fromisoformat(seen[slug]), "desc": "", "gn": False})
    path.write_text(json.dumps(seen, indent=0))
    return out


def google_trends():
    """Top US searches today with their news stories. Returns story items with a search-count signal."""
    ns = {"ht": "https://trends.google.com/trending/rss"}
    out = []
    try:
        root = ET.fromstring(get("https://trends.google.com/trending/rss?geo=US"))
    except Exception as e:
        FAILED.append(f"Google Trends ({str(e)[:40]})")
        return out
    for it in root.findall(".//item"):
        traffic = it.findtext("ht:approx_traffic", "", ns)
        for n in it.findall("ht:news_item", ns)[:1]:
            out.append({"col": "national", "title": text(n.findtext("ht:news_item_title", "", ns)),
                        "url": n.findtext("ht:news_item_url", "", ns), "source": n.findtext("ht:news_item_source", "", ns),
                        "ts": NOW, "desc": "", "gn": False, "trend": traffic, "trend_term": it.findtext("title")})
    return out


def wikipedia_top():
    """Article -> views for yesterday's most-read English Wikipedia pages."""
    d = None
    for back in (1, 2):  # yesterday's list is not published until mid-morning UTC
        y = NOW - timedelta(days=back)
        try:
            d = json.loads(get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{y:%Y/%m/%d}"))
            break
        except Exception as e:
            err = str(e)[:40]
    if d is None:
        FAILED.append(f"Wikipedia ({err})")
        return {}
    top = {}
    for a in d["items"][0]["articles"][:150]:
        name = re.sub(r"\s*\(.*\)$", "", a["article"].replace("_", " "))
        if ":" in name or name == "Main Page" or len(name) < 8 or " " not in name:
            continue
        top.setdefault(name, a["views"])
    return top


def country_airplay():
    """Billboard Country Airplay top 40 -> (artist -> rank, song -> (rank, artists)). Falls back to the last saved chart."""
    path = DATA / "chart.json"
    try:
        b = get("https://www.billboard.com/charts/country-airplay/", timeout=40)
        artists, songs = {}, {}
        for rank, row in enumerate(b.split('class="o-chart-results-list-row-container"')[1:41], 1):
            m = re.search(r'id="title-of-a-story"[^>]*>(.*?)</h3>\s*<span[^>]*>(.*?)</span>', row, re.S)
            if not m:
                continue
            who = text(m.group(2))
            songs.setdefault(text(m.group(1)), [rank, who])
            for name in re.split(r"\s+(?:Featuring|&|And|With|x|X)\s+|,\s*", who):
                name = name.strip()
                if len(name) > 3:
                    artists.setdefault(name, rank)
        if len(songs) < 30:
            raise ValueError(f"only {len(songs)} chart rows parsed")
        path.write_text(json.dumps({"pulled": NOW.isoformat(), "artists": artists, "songs": songs}, indent=1))
    except Exception as e:
        FAILED.append(f"Country Airplay chart ({str(e)[:40]}; using last saved)")
        if not path.exists():
            return {}, {}
        d = json.loads(path.read_text())
        artists, songs = d["artists"], d["songs"]
    return artists, songs


def top40_match(title, artists, songs):
    """(artist, rank) when a headline names a top-40 artist or quotes a top-40 song title."""
    hits = [(r, a) for a, r in artists.items() if re.search(r"\b" + re.escape(a) + r"\b", title)]
    for song, (r, who) in songs.items():
        if len(song) > 3 and re.search("[\u2018\u201c'\"]" + re.escape(song) + "[\u2019\u201d'\"]", title, re.I):
            hits.append((r, who))
    if not hits:
        return None
    r, a = min(hits)
    return a, r


def update_music_archive(stories, artists, songs):
    """Keep every story tied to a top-40 song forever (data/music_archive.json).
    All other music stories only live in data/music_recent.json, which each run replaces."""
    path = DATA / "music_archive.json"
    arch = json.loads(path.read_text()) if path.exists() else []
    seen = {a["id"] for a in arch} | {a["u"] for a in arch}
    recent, added = [], 0
    for it in stories:
        hit = top40_match(it["title"], artists, songs)
        e = {"id": "A" + md5((it["title"] + it["source"]).encode()).hexdigest()[:8], "t": it["title"],
             "s": it["source"], "d": it["ts"].astimezone(CT).date().isoformat(), "u": it["url"],
             "a": hit[0] if hit else "",
             "o": 1 if blocked("music", it["title"], it["desc"], it["source"]) else 0}
        if not hit:
            recent.append(e)
        elif e["id"] not in seen and e["u"] not in seen:
            e["k"] = 1
            arch.append(e)
            seen |= {e["id"], e["u"]}
            added += 1
    arch.sort(key=lambda e: e["d"], reverse=True)
    path.write_text(json.dumps(arch, indent=0, ensure_ascii=False))
    (DATA / "music_recent.json").write_text(json.dumps(recent, indent=0, ensure_ascii=False))
    return added, len(arch), len(recent)


# ---------------- clustering + scoring ----------------
STOP = set("a an the of to in on at for and or with by from is are was were be as it its this that after new over "
           "into up out about his her their your you we our mo missouri".split())


def words(t):
    return {w for w in re.findall(r"[a-z0-9']+", t.lower()) if w not in STOP and len(w) > 2}


def cluster(items):
    """Group near-identical headlines from different outlets. Keeps the best-sourced item per group."""
    groups = []
    for it in sorted(items, key=lambda x: x["ts"], reverse=True):
        w = words(it["title"])
        for g in groups:
            if g["col"] == it["col"] and w and len(w & g["w"]) / max(1, len(w | g["w"])) >= 0.55:
                g["sources"].add(it["source"])
                g["members"].append(it)
                break
        else:
            groups.append({"col": it["col"], "w": w, "sources": {it["source"]}, "members": [it]})
    out = []
    for g in groups:
        best = sorted(g["members"], key=lambda x: (x["gn"], x.get("trend") is None, -x["ts"].timestamp()))[0]
        best = dict(best)
        best["outlets"] = len(g["sources"])
        best["also"] = sorted(g["sources"] - {best["source"]})[:4]
        best["trend"] = next((m["trend"] for m in g["members"] if m.get("trend")), None)
        best["ts"] = max(m["ts"] for m in g["members"]) if best["gn"] else best["ts"]
        out.append(best)
    return out


def traffic_num(s):
    m = re.match(r"([\d,]+)", s or "")
    return int(m.group(1).replace(",", "")) if m else 0


def short_num(n):
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n // 1000}K" if n >= 1000 else str(n)


def score(it, wiki, chart):
    hours = max(0.0, (NOW - it["ts"]).total_seconds() / 3600)
    blob = f'{it["title"]} {it["desc"][:200]}'
    s = 10 + 4 * math.log2(max(1, it["outlets"]))
    signals = []
    if it.get("trend"):
        s += 3 * math.log10(max(10, traffic_num(it["trend"])))
        signals.append(f'Google searches today: {it["trend"]}')
    if it["outlets"] >= 3:
        signals.append(f'Carried by {it["outlets"]} outlets')
    for name, views in wiki.items():
        if name.lower() in blob.lower():
            s += 4
            signals.append(f"Wikipedia: {short_num(views)} reads yesterday ({name})")
            break
    if it["col"] == "music":
        hit = top40_match(it["title"], *chart)
        if hit:
            a, r = hit
            s += 6 + (40 - r) / 10
            signals.append(f"{a}: #{r} on Country Airplay")
        if it.get("near"):
            s += 12 if it["near"] == 1 else 6
    s += min(9, 3 * len(set(m.group(0).lower() for m in FUN.finditer(blob))))
    s -= 6 * len(set(m.group(0).lower() for m in DOWNER.finditer(it["title"])))
    if it["source"] in ("UPI Odd News", "Good News Network", "Upworthy"):
        s += 2
    if it["col"] == "local":
        it["prio"] = town_priority(it.get("town"), it["tier"]) if it["tier"] != 2 else 4
        s += {0: 8, 1: 6, 2: 3, 3: 0, 4: 0}[it["prio"]] + (8 if it.get("congrats") else 0)
        s -= hours / 24 * 2
    elif it["col"] == "weird":
        s += {"local": 15, "missouri": 6, "us": 0, "intl": -3}[it["scope"]]
        s -= hours / 24 * 2 if it["scope"] == "local" else hours / 6
    else:
        s -= hours / 6
    it["score"] = round(s, 1)
    it["signal"] = " · ".join(signals[:2])


# ---------------- link resolving ----------------
def resolve_gn(link, cache):
    if link in cache:
        return cache[link]
    gid = link.split("/articles/")[1].split("?")[0]
    url = None
    try:
        raw = base64.urlsafe_b64decode(gid + "=" * (-len(gid) % 4))
        m = re.search(rb"https?://[\x21-\x7e]+", raw)
        if m and not gid.startswith("AU_yqL"):
            url = m.group(0).decode()
    except Exception:
        pass
    if not url:
        page = get(f"https://news.google.com/articles/{gid}?hl=en-US&gl=US&ceid=US:en")
        sg = re.search(r'data-n-a-sg="([^"]+)"', page)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page)
        if sg and ts:
            inner = json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None,
                                                None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                                gid, int(ts.group(1)), sg.group(1)])
            body = "f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", inner, None, "generic"]]]))
            r = get("https://news.google.com/_/DotsSplashUi/data/batchexecute", body.encode(),
                    {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
            m = re.search(r'garturlres\\",\\"(https?:[^"\\]+)', r)
            url = m.group(1) if m else None
    if url:
        cache[link] = url
    return url


def page_summary(url):
    try:
        h = get(url, timeout=15)[:300000]
    except Exception:
        return ""
    for pat in (r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"',
                r'<meta[^>]+content="([^"]*)"[^>]+property="og:description"',
                r'<meta[^>]+name="description"[^>]+content="([^"]*)"'):
        m = re.search(pat, h, re.I)
        if m and len(text(m.group(1))) > 30:
            return text(m.group(1))[:400]
    return ""


def resolve_all(items, limit=None, budget_s=240):
    """Swap Google News links for publisher links. Google throttles this, so: one at a time, cached,
    2.5 s apart, a 60 s pause after each 429 (two pauses at most), and a 4-minute budget.
    Unresolved items keep the Google News link, which still opens the story in a modern browser."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    tried, pauses, start = 0, 0, time.time()
    for it in items:
        if time.time() - start > budget_s:
            FAILED.append("Google News link lookup (time budget used, rest keep Google links)")
            break
        if not it.get("gn_url") and it["url"].startswith("https://news.google.com"):
            it["gn_url"] = it["url"]
        if not it["url"].startswith("https://news.google.com"):
            continue
        tkey = f'{it["source"]}|{it["title"]}'  # Google gives one story different links in different searches
        if tkey in cache:
            it["url"] = cache[tkey]
            continue
        if it["url"] not in cache and limit is not None and tried >= limit:
            continue
        real = None
        for attempt in range(2):
            try:
                tried += it["url"] not in cache
                real = resolve_gn(it["url"], cache)
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or pauses >= 2:
                    break
                pauses += 1
                time.sleep(60)
            except Exception:
                break
        if real:
            it["url"] = real
            cache[tkey] = real
        elif pauses >= 2:
            FAILED.append("Google News link lookup (429, rest keep Google links)")
            break
        time.sleep(2.5)
    CACHE.write_text(json.dumps(cache, indent=0))


def article_text(url):
    """Paragraph text of an article page, so LOCAL PRIDE can name every recipient without a click."""
    try:
        h = get(url, timeout=15)[:600000]
    except Exception:
        return ""
    h = re.sub(r"<(nav|header|footer|aside|script|style)\b.*?</\1>", " ", h, flags=re.S | re.I)
    paras = [text(x) for x in re.findall(r"<p[^>]*>(.*?)</p>", h, re.S)]
    boiler = re.compile(r"outdated browser|subscri|password|cookie|sign up|newsletter|click here|log ?in|"
                        r"all rights reserved|advertis|copyright", re.I)
    keep = [x for x in paras if len(x.split()) >= 6 and re.search(r"[.!?\"”]$", x) and not boiler.search(x)]
    return " ".join(keep)[:2500]


def bodies(items):
    todo = [i for i in items if not i["url"].startswith("https://news.google.com") and len(i.get("desc", "")) < 600]
    with ThreadPoolExecutor(6) as ex:
        for it, body in zip(todo, ex.map(lambda i: article_text(i["url"]), todo)):
            it["body"] = body


def summaries(items):
    todo = [i for i in items if not i["desc"] and i.get("kind") != "joke"
            and not i["url"].startswith("https://news.google.com")]
    with ThreadPoolExecutor(6) as ex:
        for it, d in zip(todo, ex.map(lambda i: page_summary(i["url"]), todo)):
            it["desc"] = d


# ---------------- main ----------------
def main():
    DATA.mkdir(exist_ok=True)
    jobs =[("gn", "national", "Google News", gn(q, 1)) for q in NATIONAL_Q]
    jobs += [("feed", "national", l, u) for l, u in NATIONAL_FEEDS]
    jobs += [("gn", "local", "Google News", gn(q, d)) for q, d in LOCAL_Q]
    jobs += [("feed", "local", l, u) for l, u in LOCAL_FEEDS]
    jobs += [("gn", "music", "Google News", gn(q, 1)) for q in MUSIC_Q]
    jobs += [("feed", "music", l, u) for l, u in MUSIC_FEEDS]
    jobs += [("gn", "weird", "Google News", gn(q, d)) for q, d in WEIRD_Q]
    jobs += [("feed", "weird", l, u) for l, u in WEIRD_FEEDS]
    with ThreadPoolExecutor(6) as ex:
        raw = [it for chunk in ex.map(pull, jobs) for it in chunk]
    raw += google_trends()
    raw += lebanon_r3()
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
    import community
    raw += community.collect(sys.modules[__name__])
    wiki, chart = wikipedia_top(), country_airplay()
    import concerts
    shows = concerts.find_concerts(sys.modules[__name__], chart[0])
    raw += concerts.area_news(sys.modules[__name__], chart[0])

    # Music archive works from every music story, before the board's downer/gossip filters.
    music_all = [dict(it) for it in raw if it["col"] == "music" and it["title"]
                 and (NOW - it["ts"]).total_seconds() <= (24 * 30 if it.get("near") else FRESH_HOURS["music"]) * 3600
                 and not JUNK.search(f'{it["title"]} | {it["source"]}') and not SPAM.search(it["title"])]
    arch_added, arch_total, recent_n = update_music_archive(cluster(music_all), *chart)

    kept, dropped = [], {}
    for it in raw:
        age_h = (NOW - it["ts"]).total_seconds() / 3600
        limit = (CONGRATS_FRESH_HOURS[0] if it["col"] == "local" else 24 * 30 if it.get("near")
                 else FRESH_HOURS[it["col"]])
        if age_h > limit or not it["title"]:
            continue
        why = blocked(it["col"], it["title"], it["desc"], it["source"])
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        if it["col"] == "weird":
            town, tier = town_of(it["title"], it["desc"], it["source"])
            blob = f'{it["title"]} {it["desc"][:200]}'
            it["scope"] = ("local" if tier in (0, 1) else "missouri" if re.search(r"\bMissouri\b|\bMo\.", blob)
                           else "intl" if (FOREIGN_PLACE.search(blob) or (not US_PLACE.search(blob) and (
                               it["source"] in INTL_SOURCES or FOREIGN_SOURCE.search(it["source"])))) else "us")
            it["town"], it["tier"] = (town, tier) if it["scope"] == "local" else (None, None)
            if it["scope"] != "local" and age_h > WEIRD_AWAY_HOURS:
                continue
        if it["col"] == "local" and it.get("community"):
            pass  # town and tier come from the source itself
        elif it["col"] == "local":
            it["town"], it["tier"] = town_of(it["title"], it["desc"], it["source"])
            if it["town"] is None:
                dropped["outside area"] = dropped.get("outside area", 0) + 1
                continue
            if it["tier"] == 2:  # Springfield, Branson etc. are outside the core listening area
                dropped["outside core area"] = dropped.get("outside core area", 0) + 1
                continue
        if it["col"] == "local":
            it["congrats"] = bool(it.get("community") or CONGRATS.search(it["title"]))
            base = LEBANON_FRESH_HOURS if it["tier"] == 0 else FRESH_HOURS["local"]
            if age_h > (CONGRATS_FRESH_HOURS[it["tier"]] if it["congrats"] else base):
                continue
        kept.append(it)

    items = cluster(kept)
    # International weird news only when US outlets carry it widely or it is in Google Trends.
    items = [i for i in items if not (i["col"] == "weird" and i["scope"] == "intl" and i["outlets"] < 10 and not i.get("trend"))]
    for it in items:
        it["id"] = it["col"][0].upper() + md5((it["title"] + it["source"]).encode()).hexdigest()[:6]
        score(it, wiki, chart)

    direct = {l for l, _ in NATIONAL_FEEDS + LOCAL_FEEDS + MUSIC_FEEDS + WEIRD_FEEDS}
    short = []
    for col in ("national", "local", "music", "weird"):
        rows = sorted((i for i in items if i["col"] == col), key=lambda x: -x["score"])
        pick, per_src = [], {}
        for i in rows:  # top 3 from each direct feed first, so one hot query can't crowd them out
            if i["source"] in direct and per_src.get(i["source"], 0) < min(3, PER_SOURCE[col]):
                pick.append(i)
                per_src[i["source"]] = per_src.get(i["source"], 0) + 1
        for i in rows:
            if len(pick) >= SHORT[col]:
                break
            if i not in pick and per_src.get(i["source"], 0) < PER_SOURCE[col]:
                pick.append(i)
                per_src[i["source"]] = per_src.get(i["source"], 0) + 1
        if col == "local":  # every Lebanon item that survived the filters goes to Claude
            pick += [i for i in rows if i["tier"] == 0 and i not in pick]
        if col == "music":  # every top-40 artist story tied to our area goes to Claude
            pick += [i for i in rows if i.get("near") and i not in pick]
        if col == "weird":  # every listening-area weird story goes to Claude
            pick += [i for i in rows if i["scope"] == "local" and i not in pick]
        short += pick
    import humor
    jokes, lists = humor.collect(sys.modules[__name__])
    for it in jokes + lists:
        it["id"] = "H" + md5((it["title"] + it["source"]).encode()).hexdigest()[:6]
    short += jokes[:30] + lists[:40]
    for it in short:
        it["gn_url"] = it["url"] if it["gn"] else None
    top_gn = [i for col, n in (("local", 70), ("weird", 25), ("national", 12), ("music", 10), ("humor", 4))
              for i in sorted((x for x in short if x["col"] == col and x["gn"]), key=lambda x: -x["score"])[:n]]
    resolve_all(top_gn)
    summaries(short)
    bodies([i for i in short if i["col"] == "local" and i.get("congrats")])
    # Second pass: a resolved summary can reveal a downer the headline hid.
    short = [i for i in short if not (TRAGIC.search(i["desc"][:200]) or POLITICS.search(i["desc"][:200]))]

    pool = []
    for i in short:
        pool.append({k: i.get(k) for k in ("id", "col", "title", "source", "url", "gn_url", "desc", "outlets", "also",
                                           "signal", "score", "town", "tier", "kind", "punch", "congrats", "scope", "near", "body", "prio")} | {"ts": i["ts"].isoformat()})
    (DATA / "pool.json").write_text(json.dumps({"collected": NOW.isoformat(), "items": pool}, indent=1, ensure_ascii=False))

    print(f"raw {len(raw)} | kept {len(kept)} | stories {len(items)} | shortlist {len(pool)} | dropped {dropped}")
    print(f"music archive: +{arch_added} top-40 stories kept (total {arch_total}) | {recent_n} other music stories searchable until replaced")
    print(f"humor: {len(jokes)} jokes pass the filters | {len(lists)} show-prep topics (national days, viral, satire)")
    board_path = DATA / "music_board.json"
    board = json.loads(board_path.read_text()) if board_path.exists() else []
    print(f"music cards already up (kept up to 30 days; replace one by listing its id in music_drop): {len(board)}")
    for b in board:
        print(f'   UP | {b["id"]} | added {b["added"]} | {"NEAR US" if b.get("near") == 1 else "KC/STL" if b.get("near") == 2 else "-"} | {b["line"][:110]}')
    print(f"concerts found (top-40 artists, nearest first): {len(shows)}")
    for sh in shows:
        print(f'   CONCERT | tier {sh["tier"]} | {sh["date"]} | {sh["artist"]} (#{sh["rank"]}) | {sh["venue"]}, {sh["city"]} | {sh["event"][:70]}')
    print("FAILED: " + (", ".join(FAILED) if FAILED else "none"))
    for col in ("national", "local", "music", "humor", "weird"):
        print(f"\n=== {'MORNING NEWS ONLY' if col == 'weird' else col.upper()}")
        for i in sorted((p for p in pool if p["col"] == col), key=lambda x: -x["score"]):
            age = (NOW - datetime.fromisoformat(i["ts"])).total_seconds() / 3600
            age = f"{age:.0f}h" if age < 48 else f"{age / 24:.0f}d"
            prio = {0: "", 1: " HIGH", 2: " LOW"}.get(i.get("prio"), "")
            where = (f' [{i["town"]}{"*" if i["tier"] == 0 else ""}{prio}]{" CONGRATS?" if i.get("congrats") else ""}'
                     if col == "local" else
                     f' [{"LOCAL " + (i["town"] or "") if i["scope"] == "local" else i["scope"].upper()}]' if col == "weird" else
                     f' [{"NEAR US" if i["near"] == 1 else "KC/STL"}]' if col == "music" and i.get("near") else "")
            if i.get("kind") == "joke":
                print(f'{i["id"]} | {age} | {i["source"]} | {i["signal"]} | JOKE: {i["title"]} / {i["punch"]}')
            else:
                tag = {"day": "TODAY IS: ", "viral": "VIRAL: ", "satire": "SATIRE: "}.get(i.get("kind"), "") if col == "humor" else ""
                full = i.get("body") or i["desc"]
                summ = full[:1800] if col == "local" and i.get("congrats") else i["desc"][:220]
                print(f'{i["id"]} | {age} | {i["source"][:22]}{where} | {i["signal"] or "-"} | {tag}{i["title"]} || {summ}')


if __name__ == "__main__":
    main()
