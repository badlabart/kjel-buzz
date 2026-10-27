"""Wx column for Show Prep (Boss 2026-10-21): short general weather for the whole listening area, Marshfield to the Lake of
the Ozarks (Boss 2026-10-27: one short line per day for the week, each with its date, and the card says what area it covers),
then ONLY severe weather: active watches and warnings, one line each naming the counties and cities. Source:
api.weather.gov (free, no key).

Alerts match by county (SAME code), so a warning for part of a county lists the whole county. Advisories and statements
are left out on purpose (Boss: "only mention severe wx").
The page re-reads alerts live in the browser (page.py WX_JS), so a warning issued after the morning build still shows.
This module writes the build-time snapshot that old browsers and offline copies show. The forecast is the build's.
"""
import html
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
UA = "KJEL-showprep (badlabart on GitHub)"
NWS = "https://api.weather.gov"
MAPCLICK = "https://forecast.weather.gov/MapClick.php?lat={}&amp;lon={}"
OFFICE = "https://www.weather.gov/sgf/"  # NWS Springfield covers all nine counties

# n = county, s = SAME code (29 + county FIPS), town = the place the forecast is read for and named on air (Camden is read
# at Osage Beach and called Lake of the Ozarks), t = cities named in an alert for that county, ll = the forecast point
# and the NWS details page.
COUNTIES = [
    {"n": "Laclede", "s": "029105", "town": "Lebanon", "t": ["Lebanon"], "ll": "37.6806,-92.6638"},
    {"n": "Pulaski", "s": "029169", "town": "Waynesville", "t": ["Waynesville", "St. Robert", "Fort Leonard Wood"], "ll": "37.8281,-92.2007"},
    {"n": "Camden", "s": "029029", "town": "Lake of the Ozarks", "t": ["Camdenton", "Osage Beach", "Lake Ozark"], "ll": "38.1503,-92.6177"},
    {"n": "Miller", "s": "029131", "town": "Eldon", "t": ["Eldon"], "ll": "38.3481,-92.5813"},
    {"n": "Polk", "s": "029167", "town": "Bolivar", "t": ["Bolivar"], "ll": "37.6142,-93.4105"},
    {"n": "Webster", "s": "029225", "town": "Marshfield", "t": ["Marshfield"], "ll": "37.3392,-92.9077"},
    {"n": "Dallas", "s": "029059", "town": "Buffalo", "t": ["Buffalo"], "ll": "37.6439,-93.0929"},
    {"n": "Hickory", "s": "029085", "town": "Hermitage", "t": ["Hermitage"], "ll": "37.9395,-93.3180"},
    {"n": "Wright", "s": "029229", "town": "Hartville", "t": ["Hartville"], "ll": "37.2517,-92.5107"},
]
DAYS = 7  # today plus six more: the NWS hourly forecast runs about 6 1/2 days
PARTS = (("morning", range(6, 12)), ("afternoon", range(12, 18)), ("tonight", range(18, 24)))
RAIN_MIN = 30   # percent: lowest rain chance worth naming
DAY_SKY = ("Sunny", "Mostly sunny", "Partly sunny", "Mostly cloudy", "Cloudy")
NIGHT_SKY = ("Clear", "Mostly clear", "Partly cloudy", "Mostly cloudy", "Cloudy")
KINDS = (("freezing", "freezing rain"), ("sleet", "sleet"), ("snow", "snow"), ("thunder", "storms"))


def get(url, tries=3):
    """The NWS answers 503 now and then; try again before giving up so a town does not drop out of the forecast."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/geo+json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if i == tries - 1 or (isinstance(e, urllib.error.HTTPError) and e.code < 500):
                raise
            time.sleep(2)


# ---------------------------------------------------------------- severe weather
def is_severe(event):
    return event.endswith("Warning") or event.endswith("Watch")


def clock(dt):
    """"7 PM (Thu 10/22)" or "7:30 PM (Thu 10/22)": the date always follows the time (Boss 2026-10-21)."""
    t = dt.astimezone(CT)
    return f"{t.strftime('%-I %p' if t.minute == 0 else '%-I:%M %p')} ({t.strftime('%a')} {t.month}/{t.day})"


def counties_text(hit):
    if len(hit) == len(COUNTIES):
        return "entire listening area"
    return "; ".join(html.escape(c["n"]) + " county" + (f' ({html.escape(", ".join(c["t"]))})' if c["t"] else "") for c in hit)


def alert_card(p, hit):
    ev = p["event"]
    cls = "wxw" if ev.endswith("Warning") else "wxt"
    end = p.get("ends") or p.get("expires")
    until = f" until {clock(datetime.fromisoformat(end))}" if end else ""
    lat, lon = hit[0]["ll"].split(",")
    return (f'<div class="card {cls}"><div class="name"><span class="label">{html.escape(ev)}:</span> {counties_text(hit)}{until}</div>'
            f'<a class="link" href="{MAPCLICK.format(lat, lon)}" target="_blank" rel="noopener">NWS details &#8599;</a></div>')


def alerts():
    """Cards for every active watch and warning that touches one of our counties, warnings first."""
    found = []
    for f in get(f"{NWS}/alerts/active?status=actual&area=MO")["features"]:
        p = f["properties"]
        same = set((p.get("geocode") or {}).get("SAME", []))
        hit = [c for c in COUNTIES if c["s"] in same]
        if p.get("status") == "Actual" and hit and is_severe(p["event"]):
            found.append((p, hit))
    found.sort(key=lambda a: 0 if a[0]["event"].endswith("Warning") else 1)  # stable: NWS order holds within a class
    return [alert_card(p, hit) for p, hit in found]


# ---------------------------------------------------------------- general weather
def is_wet(p):
    return any(w in p["shortForecast"].lower() for w in ("rain", "shower", "storm", "snow", "sleet", "drizzle", "freezing"))


def sky_score(p):
    """0 sunny .. 4 cloudy for one hour, or None when the hour says nothing about sky (fog, a slight chance of a shower)."""
    t = p["shortForecast"].lower()
    pop = (p.get("probabilityOfPrecipitation") or {}).get("value") or 0
    if any(w in t for w in ("fog", "haze", "smoke", "mist")):
        return None
    if is_wet(p):
        return 4 if pop >= 50 else None
    if "partly" in t:
        return 2
    if "mostly sunny" in t or "mostly clear" in t:
        return 1
    if "sunny" in t or "clear" in t:
        return 0
    return 3 if "mostly cloudy" in t else 4


def kind_of(texts):
    low = " ".join(texts).lower()
    for key, name in KINDS:
        if key in low:
            return name
    return "rain"


def day_view(periods, day, now, sky_hours):
    """What one town gets on one day (for today, the hours still to come): average sky score, afternoon high, and rain by part of the day."""
    hrs = []
    for p in periods:
        t = datetime.fromisoformat(p["startTime"])
        if t.date() == day and t + timedelta(hours=1) > now:
            hrs.append((t.hour, p))
    # Sky describes the dry hours; rain is its own line. A day that is wet all day reads "cloudy".
    dry, wet = [], []
    for h, p in hrs:
        s = sky_score(p) if h in sky_hours else None
        if s is not None:
            (wet if is_wet(p) else dry).append(s)
    scores = dry or wet
    highs = [p["temperature"] for h, p in hrs if 12 <= h < 18]
    rain = {}
    for name, rng in PARTS:
        wet = [p for h, p in hrs if h in rng and ((p.get("probabilityOfPrecipitation") or {}).get("value") or 0) >= RAIN_MIN]
        if wet:
            pop = max(p["probabilityOfPrecipitation"]["value"] for p in wet)
            rain[name] = (pop, kind_of([p["shortForecast"] for p in wet]))
    return {"sky": sum(scores) / len(scores) if scores else None, "high": max(highs) if highs else None, "rain": rain}


def sky_label(avg, labels):
    return labels[0 if avg < 0.5 else 1 if avg < 1.5 else 2 if avg < 2.5 else 3 if avg < 3.5 else 4]


def pct(pops):
    lo, hi = min(pops), max(pops)
    return f"{lo}%" if lo == hi else f"{lo}-{hi}%"


def summarize(views, now, ahead=False):
    """Two short lines for the whole area on one day: sky (with highs), then who gets rain and when ("" when dry).
    ahead=True is a day after today; today reads "tonight" after 5 PM and shows highs only before 1 PM."""
    tonight = (not ahead) and now.hour >= 17
    labels = NIGHT_SKY if tonight else DAY_SKY
    avgs = [v["sky"] for _, v in views if v["sky"] is not None]
    line1 = ""
    if avgs:
        lo, hi = sky_label(min(avgs), labels), sky_label(max(avgs), labels)
        line1 = (lo if lo == hi else f"{lo} to {hi.lower()}") + (" tonight" if tonight else "")
        highs = [v["high"] for _, v in views if v["high"] is not None]
        if highs and (ahead or now.hour < 13):
            line1 += f", highs {min(highs)}" + (f"-{max(highs)}" if max(highs) != min(highs) else "")
        line1 += "."
    return [l for l in (line1, rain_line(views)) if l]


RAIN_ORDER = ("freezing rain", "sleet", "snow", "storms", "rain")  # the worst kind in a group names the group


def rain_line(views):
    """Who gets rain and when, as short as it can be: "Waynesville 70% rain afternoon." One segment per part of the day,
    neighbors that read the same are joined ("afternoon and tonight"); a place list becomes "Entire area" or "Most of the
    area" when that is true. "" when it is dry."""
    n, order, segs = len(views), [p for p, _ in PARTS], []
    for part in order:
        wet = sorted(((v["rain"][part][0], t, v["rain"][part][1]) for t, v in views if part in v["rain"]), key=lambda w: -w[0])
        if not wet:
            continue
        kinds = {k for _, _, k in wet}
        kind = next(k for k in RAIN_ORDER if k in kinds)
        who = "Entire area" if len(wet) == n else "Most of the area" if len(wet) * 3 >= n * 2 else ", ".join(t for _, t, _ in wet)
        pop = wet[0][0]
        if segs and segs[-1]["who"] == who and segs[-1]["kind"] == kind and order.index(part) == order.index(segs[-1]["parts"][-1]) + 1:
            segs[-1]["parts"].append(part)
            segs[-1]["pop"] = max(segs[-1]["pop"], pop)
        else:
            segs.append({"who": who, "kind": kind, "pop": pop, "parts": [part]})
    bits = []
    for s in segs:
        when = "all day" if len(s["parts"]) == len(PARTS) else " and ".join(s["parts"])
        bits.append(f"{s['who']} {s['pop']}% {s['kind']} {when}")
    return "; ".join(bits) + "." if bits else ""


def forecast_card(now, stamp):
    """One short line per day for the week, each with its date (the page adds TODAY / TOMORROW and drops days gone by).
    Every line is the whole area: one forecast point per county, from Marshfield to the Lake of the Ozarks."""
    hourly, failed = {}, []
    for c in COUNTIES:
        try:
            pt = get(f"{NWS}/points/{c['ll']}")["properties"]
            hourly[c["town"]] = get(pt["forecastHourly"])["properties"]["periods"]
        except Exception as e:
            failed.append(f"{c['town']} forecast ({str(e)[:40]})")
    rows = []
    for i in range(DAYS):
        day = now.date() + timedelta(days=i)
        ahead = i > 0
        sky_hours = range(18, 24) if (not ahead and now.hour >= 17) else range(7, 18)
        views = [(t, day_view(p, day, now, sky_hours)) for t, p in hourly.items()]
        views = [(t, v) for t, v in views if v["sky"] is not None or v["rain"] or v["high"] is not None]
        text = " ".join(summarize(views, now, ahead)) if views else ""
        if text:
            rows.append(f'<div class="wxd" data-date="{day.isoformat()}"><span class="dl">{day.strftime("%a").upper()} {day.month}/{day.day}</span> '
                        f'{html.escape(text)}</div>')
    if not rows:
        rows = ['<div class="wxl">Forecast unavailable. Use the link below.</div>']
    towns = ", ".join(c["town"] for c in COUNTIES if c["town"] in hourly)
    return (f'<div class="card wxf"><div class="when">AREA FORECAST <span class="src">&middot; Marshfield to Lake of the Ozarks</span></div>'
            f'{"".join(rows)}'
            f'<div class="sig">Read at {html.escape(towns)}. NWS, {stamp} &middot; '
            f'<a class="link" href="{OFFICE}" target="_blank" rel="noopener">Full forecast &#8599;</a></div></div>'), failed


NO_ALERTS = '<div class="wxok">No watches or warnings.</div>'


def column():
    """Wx column for page.write: its own HTML, an alert count for the badge, and the county table the page script needs."""
    now = datetime.now(CT)
    stamp = now.strftime("%-I:%M %p")
    failed = []
    try:
        cards = alerts()
        alert_html = "".join(cards) or NO_ALERTS
    except Exception as e:
        failed.append(f"NWS alerts ({str(e)[:40]})")
        cards = []
        alert_html = ('<div class="card wxi"><div class="name">Alerts could not be loaded.</div>'
                      f'<a class="link" href="{OFFICE}" target="_blank" rel="noopener">Check weather.gov &#8599;</a></div>')
    fc, fc_failed = forecast_card(now, stamp)
    failed += fc_failed
    conf = json.dumps([{k: c[k] for k in ("n", "s", "t", "ll")} for c in COUNTIES])
    return {"key": "wx", "name": "Wx", "cards": [], "count": len(cards), "failed": failed, "conf": conf,
            "html": f'<div class="sub" id="wxstamp">Alerts as of {stamp}</div><div id="wxalerts">{alert_html}</div>{fc}'}
