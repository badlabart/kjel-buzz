"""Wx column for Show Prep (Boss 2026-10-21): two lines of general weather for the whole listening area (sky, then who gets
rain and when), then ONLY severe weather: active watches and warnings, one line each. Source: api.weather.gov (free, no key).

Alerts match by county (SAME code), so a warning for part of a county lists the whole county. Advisories and statements
are left out on purpose (Boss: "only mention severe wx").
The page re-reads alerts live in the browser (page.py WX_JS), so a warning issued after the morning build still shows.
This module writes the build-time snapshot that old browsers and offline copies show. The forecast is the build's.
"""
import html
import json
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
UA = "KJEL-showprep (badlabart on GitHub)"
NWS = "https://api.weather.gov"
MAPCLICK = "https://forecast.weather.gov/MapClick.php?lat={}&amp;lon={}"
OFFICE = "https://www.weather.gov/sgf/"  # NWS Springfield covers all nine counties

# n = county, s = SAME code (29 + county FIPS), town = the place we name on air for that county, ll = its point
# (forecast point and NWS details page).
COUNTIES = [
    {"n": "Laclede", "s": "029105", "town": "Lebanon", "ll": "37.6806,-92.6638"},
    {"n": "Pulaski", "s": "029169", "town": "Waynesville", "ll": "37.8281,-92.2007"},
    {"n": "Camden", "s": "029029", "town": "Camdenton", "ll": "37.9962,-92.7446"},
    {"n": "Miller", "s": "029131", "town": "Eldon", "ll": "38.3481,-92.5813"},
    {"n": "Polk", "s": "029167", "town": "Bolivar", "ll": "37.6142,-93.4105"},
    {"n": "Webster", "s": "029225", "town": "Marshfield", "ll": "37.3392,-92.9077"},
    {"n": "Dallas", "s": "029059", "town": "Buffalo", "ll": "37.6439,-93.0929"},
    {"n": "Hickory", "s": "029085", "town": "Hermitage", "ll": "37.9395,-93.3180"},
    {"n": "Wright", "s": "029229", "town": "Hartville", "ll": "37.2517,-92.5107"},
]
PARTS = (("morning", range(6, 12)), ("afternoon", range(12, 18)), ("tonight", range(18, 24)))
RAIN_MIN = 30   # percent: lowest rain chance worth naming
LIKELY = 60     # percent: "likely" tier, kept apart from "chance" so one line never blends 30% with 70%
DAY_SKY = ("Sunny", "Mostly sunny", "Partly sunny", "Mostly cloudy", "Cloudy")
NIGHT_SKY = ("Clear", "Mostly clear", "Partly cloudy", "Mostly cloudy", "Cloudy")
KINDS = (("freezing", "freezing rain"), ("sleet", "sleet"), ("snow", "snow"), ("thunder", "storms"))


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/geo+json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


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
    names = ", ".join(html.escape(c["n"]) for c in hit)
    return f"{names} county" if len(hit) == 1 else f"{names} counties"


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


def town_view(periods, now, sky_hours):
    """What one town gets for the rest of today: average sky score, afternoon high, and rain by part of the day."""
    hrs = []
    for p in periods:
        t = datetime.fromisoformat(p["startTime"])
        if t.date() == now.date() and t + timedelta(hours=1) > now:
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


def summarize(views, now):
    """Two lines for the whole area: sky (with highs in the morning), then who gets rain and when."""
    tonight = now.hour >= 17
    labels = NIGHT_SKY if tonight else DAY_SKY
    avgs = [v["sky"] for _, v in views if v["sky"] is not None]
    line1 = ""
    if avgs:
        lo, hi = sky_label(min(avgs), labels), sky_label(max(avgs), labels)
        line1 = (lo if lo == hi else f"{lo} to {hi.lower()}") + (" tonight" if tonight else " today")
        highs = [v["high"] for _, v in views if v["high"] is not None]
        if highs and now.hour < 13:
            line1 += f", highs {min(highs)}" + (f"-{max(highs)}" if max(highs) != min(highs) else "")
        line1 += "."
    order = [n for n, _ in PARTS]
    groups = rain_groups(views, True)
    if len(groups) > 4:  # too many pieces for one line: stop splitting likely from chance
        groups = rain_groups(views, False)
    groups.sort(key=lambda g: (min(order.index(p) for p in g["parts"]), -max(p for p, _ in g["items"])))
    bits = []
    for g in groups:
        g["items"].sort(key=lambda it: -it[0])
        who = "Entire area" if len(g["items"]) == len(views) else ", ".join(t for _, t in g["items"])
        parts = sorted(g["parts"], key=order.index)
        when = "all day" if len(parts) == len(PARTS) else " and ".join(parts)
        bits.append(f"{who} {pct([p for p, _ in g['items']])} {g['kind']} {when}")
    line2 = "; ".join(bits) + "." if bits else "No rain expected."
    return [l for l in (line1, line2) if l]


def rain_groups(views, split):
    """Towns with the same kind and chance of precipitation share a group; a group that repeats across parts of the day
    becomes one group ("afternoon and tonight"). split=True keeps likely (60%+) apart from chance (30-50%)."""
    by_part = {}
    for town, v in views:
        for part, (pop, kind) in v["rain"].items():
            by_part.setdefault((part, kind, split and pop >= LIKELY), []).append((pop, town))
    joined = {}
    for (part, kind, likely), items in by_part.items():
        sig = (kind, likely, tuple(sorted((t, p) for p, t in items)))
        joined.setdefault(sig, {"kind": kind, "items": items, "parts": []})["parts"].append(part)
    return list(joined.values())


def forecast_card(now, stamp):
    views, failed = [], []
    sky_hours = range(18, 24) if now.hour >= 17 else range(7, 18)
    for c in COUNTIES:
        try:
            pt = get(f"{NWS}/points/{c['ll']}")["properties"]
            views.append((c["town"], town_view(get(pt["forecastHourly"])["properties"]["periods"], now, sky_hours)))
        except Exception as e:
            failed.append(f"{c['town']} forecast ({str(e)[:40]})")
    lines = "".join(f'<div class="wxl">{html.escape(l)}</div>' for l in summarize(views, now)) if views else ""
    if not lines:
        lines = '<div class="wxl">Forecast unavailable. Use the link below.</div>'
    return (f'<div class="card wxf">{lines}<div class="sig">NWS forecast, {stamp} &middot; '
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
    conf = json.dumps([{k: c[k] for k in ("n", "s", "ll")} for c in COUNTIES])
    return {"key": "wx", "name": "Wx", "cards": [], "count": len(cards), "failed": failed, "conf": conf,
            "html": f'<div class="sub" id="wxstamp">Alerts as of {stamp}</div><div id="wxalerts">{alert_html}</div>{fc}'}
