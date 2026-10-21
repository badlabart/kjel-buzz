"""Wx column for Show Prep (Boss 2026-10-21): active National Weather Service alerts for the listening area, then a
one-line-per-town forecast for today. Source: api.weather.gov (free, no key).

Alerts are matched by county (SAME code), so a warning that covers only part of a county still lists the whole county.
The page re-reads alerts live in the browser (page.py WX_JS), so a warning issued after the morning build still shows.
This module writes the build-time snapshot that old browsers and offline copies show.
"""
import html
import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
UA = "KJEL-showprep (badlabart on GitHub)"
NWS = "https://api.weather.gov"
MAPCLICK = "https://forecast.weather.gov/MapClick.php?lat={}&amp;lon={}"
OFFICE = "https://www.weather.gov/sgf/"  # NWS Springfield covers all nine counties

# n = county, s = SAME code (29 + county FIPS), ll = point for the NWS details page, t = towns we name on air
COUNTIES = [
    {"n": "Laclede", "s": "029105", "ll": "37.6806,-92.6638", "t": ["Lebanon"]},
    {"n": "Pulaski", "s": "029169", "ll": "37.8203,-92.1696", "t": ["Waynesville", "St. Robert", "Fort Leonard Wood"]},
    {"n": "Camden", "s": "029029", "ll": "37.9962,-92.7446", "t": ["Camdenton", "Osage Beach"]},
    {"n": "Miller", "s": "029131", "ll": "38.3481,-92.5813", "t": ["Eldon"]},
    {"n": "Polk", "s": "029167", "ll": "37.6142,-93.4105", "t": ["Bolivar"]},
    {"n": "Webster", "s": "029225", "ll": "37.3392,-92.9077", "t": ["Marshfield"]},
    {"n": "Dallas", "s": "029059", "ll": "37.6439,-93.0929", "t": ["Buffalo"]},
    {"n": "Hickory", "s": "029085", "ll": "37.9395,-93.3180", "t": ["Hermitage"]},
    {"n": "Wright", "s": "029229", "ll": "37.2517,-92.5107", "t": []},
]
# Forecast towns: Lebanon plus Boss's high-priority towns (collect.HIGH_TOWNS). Towns with the same forecast share a line.
TOWNS = [("Lebanon", "37.6806,-92.6638"), ("Waynesville", "37.8281,-92.2007"), ("St. Robert", "37.8203,-92.1696"),
         ("Fort Leonard Wood", "37.7436,-92.1294"), ("Camdenton", "37.9962,-92.7446"), ("Osage Beach", "38.1503,-92.6177"),
         ("Eldon", "38.3481,-92.5813"), ("Bolivar", "37.6142,-93.4105"), ("Marshfield", "37.3392,-92.9077")]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/geo+json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def clock(dt, today):
    t = dt.astimezone(CT)
    s = t.strftime("%-I:%M %p")
    return s if t.date() == today else t.strftime("%a ") + s


def rank(event):
    return 0 if event.endswith("Warning") else 1 if event.endswith("Watch") else 2


def covers(hit):
    if len(hit) == len(COUNTIES):
        return "Entire listening area"
    return " &middot; ".join(html.escape(c["n"]) + " Co." + (f' ({html.escape(", ".join(c["t"]))})' if c["t"] else "") for c in hit)


def alert_card(p, hit, today):
    ev = p["event"]
    cls = "wxw" if ev.endswith("Warning") else "wxt" if ev.endswith("Watch") else "wxi"
    end = p.get("ends") or p.get("expires")
    until = f' <span class="src">&middot; until {clock(datetime.fromisoformat(end), today)}</span>' if end else ""
    lat, lon = hit[0]["ll"].split(",")
    return (f'<div class="card {cls}"><div class="when">{html.escape(ev.upper())}{until}</div>'
            f'<div class="name">{covers(hit)}</div>'
            f'<a class="link" href="{MAPCLICK.format(lat, lon)}" target="_blank" rel="noopener">NWS details &#8599;</a></div>')


def alerts(today):
    """(cards, count) for every active alert that touches one of our counties, warnings first."""
    found = []
    for f in get(f"{NWS}/alerts/active?status=actual&area=MO")["features"]:
        p = f["properties"]
        same = set((p.get("geocode") or {}).get("SAME", []))
        hit = [c for c in COUNTIES if c["s"] in same]
        if p.get("status") == "Actual" and hit:
            found.append((p, hit))
    found.sort(key=lambda a: rank(a[0]["event"]))  # stable: NWS order holds within a class
    return [alert_card(p, hit, today) for p, hit in found]


def town_text(periods, today):
    day = night = None
    for p in periods:
        if datetime.fromisoformat(p["startTime"]).date() != today:
            continue
        if p["isDaytime"]:
            day = day or p
        else:
            night = night or p
    main = day or night
    if not main:
        return None
    bits = [main["shortForecast"]]
    if day:
        bits.append(f"Hi {day['temperature']}")
    if night:
        bits.append(f"Lo {night['temperature']}")
    dpop = (day or {}).get("probabilityOfPrecipitation", {}).get("value") or 0
    npop = (night or {}).get("probabilityOfPrecipitation", {}).get("value") or 0
    if dpop >= 30:
        bits.append(f"Rain {dpop}%")
    elif npop >= 30:
        bits.append(f"Rain {npop}% tonight")
    return " &middot; ".join(html.escape(b) for b in bits)


def forecast_card(today, stamp):
    groups, failed = {}, []
    for name, ll in TOWNS:
        try:
            pt = get(f"{NWS}/points/{ll}")["properties"]
            text = town_text(get(pt["forecast"])["properties"]["periods"], today)
        except Exception as e:
            failed.append(f"{name} forecast ({str(e)[:40]})")
            continue
        if text:
            groups.setdefault(text, []).append(name)
    lines = "".join(f'<div class="wxl"><b>{html.escape(", ".join(n))}</b> {t}</div>' for t, n in groups.items())
    if not lines:
        lines = '<div class="wxl">Forecast unavailable. Use the link below.</div>'
    return (f'<div class="card wxf"><div class="when">TODAY <span class="src">&middot; NWS forecast, {stamp}</span></div>{lines}'
            f'<a class="link" href="{OFFICE}" target="_blank" rel="noopener">Full forecast &#8599;</a></div>'), failed


def column():
    """Wx column for page.write: its own HTML, an alert count for the badge, and the county table the page script needs."""
    now = datetime.now(CT)
    today, stamp = now.date(), now.strftime("%-I:%M %p")
    failed = []
    try:
        cards = alerts(today)
        alert_html = "".join(cards) or '<div class="card wxn"><div class="name">No active alerts for the listening area.</div></div>'
    except Exception as e:
        failed.append(f"NWS alerts ({str(e)[:40]})")
        cards = []
        alert_html = ('<div class="card wxi"><div class="name">Alerts could not be loaded.</div>'
                      f'<a class="link" href="{OFFICE}" target="_blank" rel="noopener">Check weather.gov &#8599;</a></div>')
    fc, fc_failed = forecast_card(today, stamp)
    failed += fc_failed
    return {"key": "wx", "name": "Wx", "cards": [], "count": len(cards), "failed": failed, "conf": json.dumps(COUNTIES),
            "html": f'<div class="sub" id="wxstamp">Alerts as of {stamp}</div><div id="wxalerts">{alert_html}</div>{fc}'}
