"""Write the Buzz Report as one plain HTML file (no modern JS/CSS needed) -> docs/index.html and index.html.

Same look as the KJEL Event Board. Old browsers show every card from the HTML itself.
A tiny ES3 script turns timestamps into "5H AGO" and warns when the report is stale.
"""
import html
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CT = ZoneInfo("America/Chicago")

CSS = """
body{margin:0;background:#0A2A50;color:#0A2A50;font-family:Arial,Helvetica,sans-serif;font-size:15px}
.top{background:#FFFFFF;border-bottom:5px solid #FDB913;padding:10px 18px}
.logo{font-style:italic;font-weight:bold;font-size:28px;display:inline-block;vertical-align:middle;margin-right:14px}
.star{color:#FDB913;font-style:normal}.call{color:#D0101F}
.hd{display:inline-block;vertical-align:middle}
.title{font-weight:bold;font-size:20px}.meta{font-size:13px;color:#33445C}
.stale{display:none;background:#D0101F;color:#FFFFFF;font-weight:bold;font-size:13px;padding:6px 18px}
.board{white-space:nowrap;overflow-x:auto;padding:12px 6px}
.col{display:inline-block;vertical-align:top;white-space:normal;box-sizing:border-box;width:32.4%;min-width:280px;margin:0 5px;background:#E6E9EE;border-radius:12px;padding:0 8px 4px}
.col h2{margin:0;padding:10px 4px 2px;font-size:17px}
.sub{font-size:12px;font-weight:bold;padding:0 4px 8px;color:#33445C}
.sub.short{color:#D0101F}
.count{float:right;background:#D0101F;color:#FFFFFF;font-size:12px;padding:1px 8px;border-radius:10px}
.card{background:#FFFFFF;border:1px solid #C9CFD8;border-radius:8px;padding:8px 10px;margin-bottom:8px}
.card.new{background:#FFF1C2;border-color:#FDB913}
.when{font-size:12px;font-weight:bold;color:#D0101F}
.src{color:#33445C;font-weight:normal}
.name{font-weight:bold;font-size:15px;margin:3px 0 2px}
.town{background:#0A2A50;color:#FFFFFF;font-size:11px;font-weight:bold;padding:1px 6px;border-radius:3px;margin-right:4px}
.town.leb{background:#FDB913;color:#0A2A50}
.why{font-size:13px;margin-top:4px}
.sig{font-size:12px;margin-top:4px;color:#33445C}
.sig b{color:#D0101F}
.link{display:inline-block;margin-top:6px;font-size:12px;font-weight:bold;color:#0A2A50}
.empty{font-size:13px;color:#33445C;padding:4px 4px 10px}
"""

# ES3 only: no let/const, arrow functions, classList, or dataset.
JS = """
(function(){
  var now=new Date().getTime(), divs=document.getElementsByTagName('div');
  for(var i=0;i<divs.length;i++){
    var c=divs[i]; if(c.className.indexOf('card')!==0) continue;
    var ts=parseInt(c.getAttribute('data-ts'),10); if(!ts) continue;
    var h=Math.floor((now-ts)/3600000), w=c.getElementsByTagName('span')[0], label;
    if(h<1) label='JUST IN'; else if(h<24) label=h+'H AGO'; else if(h<48) label='YESTERDAY'; else label=Math.floor(h/24)+' DAYS AGO';
    if(w) w.innerHTML=label;
    if(h<12) c.className='card new';
  }
  var u=parseInt(document.body.getAttribute('data-updated'),10);
  if(u && now-u>30*3600000){var s=document.getElementById('stale'); if(s) s.style.display='block';}
})();
"""


def ts_ms(iso):
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def static_when(iso):
    return datetime.fromisoformat(iso).astimezone(CT).strftime("%a %b %-d").upper()


def write(data):
    esc = html.escape
    cols = []
    for col in data["columns"]:
        cards = []
        for c in col["cards"]:
            town = ""
            if col["key"] == "local" and c.get("town"):
                town = f'<span class="town{" leb" if c.get("tier") == 0 else ""}">{esc(c["town"])}</span>'
            sig = f'<div class="sig"><b>BUZZ:</b> {esc(c["signal"])}</div>' if c.get("signal") else ""
            why = f'<div class="why">{esc(c["line"])}</div>' if c.get("line") else ""
            cards.append(
                f'<div class="card" data-ts="{ts_ms(c["ts"])}">'
                f'<div class="when"><span>{static_when(c["ts"])}</span> <span class="src">&middot; {esc(c["source"])}</span></div>'
                f'<div class="name">{town}{esc(c["title"])}</div>{why}{sig}'
                f'<a class="link" href="{esc(c["url"])}" target="_blank" rel="noopener">Read story &#8599;</a></div>')
        body = "".join(cards) or '<div class="empty">Nothing worth airing today.</div>'
        sub = ""
        if col["key"] == "local":
            lb = data["lebanon"]
            short = lb["of"] and lb["count"] < round(lb["goal"] * lb["of"])
            sub = (f'<div class="sub{" short" if short else ""}">Lebanon {lb["count"]} of {lb["of"]}'
                   f' &middot; goal {round(lb["goal"] * 100)}%{" &middot; short today" if short else ""}</div>')
        cols.append(f'<div class="col"><h2>{esc(col["name"])} <span class="count">{len(col["cards"])}</span></h2>'
                    f'{sub}{body}</div>')

    updated = datetime.fromisoformat(data["updated"])
    stamp = updated.astimezone(CT).strftime("%a %b %-d, %-I:%M %p")
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KJEL Buzz Report</title><style>{CSS}</style></head>
<body data-updated="{int(updated.timestamp() * 1000)}">
<div class="top"><div class="logo">103<span class="star">&#9733;</span>7 <span class="call">KJEL</span></div>
<div class="hd"><div class="title">The Buzz</div>
<div class="meta">KJEL Buzz Report &middot; updated {esc(stamp)}</div></div></div>
<div class="stale" id="stale">This report is more than a day old. The 6 AM refresh did not run.</div>
<div class="board">{"".join(cols)}</div>
<script>{JS}</script>
</body></html>
"""
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "index.html").write_text(page)
    (ROOT / "index.html").write_text(page)
