"""Write the Buzz Report as one plain HTML file (no modern JS/CSS needed) -> docs/index.html and index.html.

Same look as the KJEL Event Board. Old browsers show every card from the HTML itself.
A tiny ES3 script turns timestamps into "5H AGO" and warns when the report is stale.
"""
import html
from datetime import date, datetime, timezone
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
.col{display:inline-block;vertical-align:top;white-space:normal;box-sizing:border-box;width:16.2%;min-width:240px;margin:0 3px;background:#E6E9EE;border-radius:12px;padding:0 8px 4px}
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
.city{color:#33445C;white-space:nowrap}.city.leb{background:#FDB913;color:#0A2A50;padding:0 3px;border-radius:3px}
.why{font-size:13px;margin-top:4px}
.sig{font-size:12px;margin-top:4px;color:#33445C}
.sig b{color:#D0101F}
.link{display:inline-block;margin-top:6px;font-size:12px;font-weight:bold;color:#0A2A50}
.empty{font-size:13px;color:#33445C;padding:4px 4px 10px}
.punch{font-size:14px;margin-top:4px;font-style:italic}
.search{margin:0 0 8px;padding:0 2px}
.search input{font-size:14px;padding:5px 6px;border:1px solid #C9CFD8;border-radius:6px}
.search .q{width:62%}
.search .go{background:#D0101F;color:#FFFFFF;border-color:#D0101F;font-weight:bold;cursor:pointer}
.results{display:none}
.tag{font-size:10px;font-weight:bold;padding:1px 5px;border-radius:3px;margin-right:4px;vertical-align:middle}
.tag.keep{background:#FDB913;color:#0A2A50}.label{color:#D0101F;text-transform:uppercase}.card.concert{border-left:5px solid #D0101F}.tag.cong{background:#0A2A50;color:#FDB913}.tag.off{background:#D0101F;color:#FFFFFF}
"""

# ES3 only: no let/const, arrow functions, classList, or dataset.
SEARCH_JS = """
var KJ_WANT=null, KJ_ASKED=false;
function kjEsc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function kjLoad(cb){
  if(window.KJEL_MUSIC){cb();return;}
  KJ_WANT=cb; if(KJ_ASKED) return; KJ_ASKED=true;
  var s=document.createElement('script'); s.src='music_search.js?v='+document.body.getAttribute('data-updated'); s.charset='utf-8';
  s.onload=s.onreadystatechange=function(){
    if(this.readyState && this.readyState!=='loaded' && this.readyState!=='complete') return;
    s.onload=s.onreadystatechange=null; if(KJ_WANT){var f=KJ_WANT; KJ_WANT=null; f();}
  };
  document.getElementsByTagName('head')[0].appendChild(s);
}
function kjClear(){
  document.getElementById('kjq').value=''; document.getElementById('kjres').style.display='none';
  document.getElementById('kjcards').style.display='block'; return false;
}
function kjSearch(){
  var q=document.getElementById('kjq').value.replace(/^\\s+|\\s+$/g,'').toLowerCase();
  var box=document.getElementById('kjres'), cards=document.getElementById('kjcards');
  if(!q) return kjClear();
  box.style.display='block'; cards.style.display='none'; box.innerHTML='<div class="empty">Searching...</div>';
  kjLoad(function(){
    var all=window.KJEL_MUSIC||[], hits=[], i, h;
    for(i=0;i<all.length;i++){ if((all[i].t+' '+all[i].a).toLowerCase().indexOf(q)>=0) hits.push(all[i]); }
    h='<div class="sub">'+hits.length+(hits.length===1?' story':' stories')+' for &quot;'+kjEsc(q)+'&quot; &middot; <a href="#" onclick="return kjClear();">back to board</a></div>';
    if(!hits.length) h+='<div class="empty">No news found. Try the last name only.</div>';
    for(i=0;i<hits.length && i<60;i++){
      var e=hits[i];
      h+='<div class="card"><div class="when">'+kjEsc(e.d)+' <span class="src">&middot; '+kjEsc(e.s)+'</span></div>'
        +'<div class="name">'+(e.k?'<span class="tag keep">TOP 40</span>':'')+(e.o?'<span class="tag off">NOT ON BOARD</span>':'')+kjEsc(e.t)+'</div>'
        +'<a class="link" href="'+kjEsc(e.u)+'" target="_blank" rel="noopener">Read story &#8599;</a></div>';
    }
    box.innerHTML=h;
  });
  return false;
}
"""

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
  // Dated cards (events, concerts): hide anything already past; label today and tomorrow.
  function p2(n){return (n<10?'0':'')+n;}
  function iso(d){return d.getFullYear()+'-'+p2(d.getMonth()+1)+'-'+p2(d.getDate());}
  var t0=new Date(), today=iso(t0), tmr=iso(new Date(t0.getFullYear(),t0.getMonth(),t0.getDate()+1));
  for(var k=0;k<divs.length;k++){
    var e=divs[k], dd=e.getAttribute('data-date'); if(!dd) continue;
    if(dd<today){e.style.display='none';continue;}
    var sp=e.getElementsByTagName('span'), dl=null;
    for(var m=0;m<sp.length;m++){ if(sp[m].className==='dl'){dl=sp[m];break;} }
    if(dd===today){ if(dl) dl.innerHTML='TODAY &middot; '+dl.innerHTML; e.className=e.className+' new'; }
    else if(dd===tmr && dl){ dl.innerHTML='TOMORROW &middot; '+dl.innerHTML; }
  }
  var u=parseInt(document.body.getAttribute('data-updated'),10);
  if(u && now-u>30*3600000){var s=document.getElementById('stale'); if(s) s.style.display='block';}
})();
"""


def ts_ms(iso):
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def static_when(iso):
    return datetime.fromisoformat(iso).astimezone(CT).strftime("%a %b %-d").upper()


def write(data, title="The Buzz", doc_title="KJEL Buzz Report", subdir=""):
    """subdir="" writes the Buzz (docs/index.html); subdir="news" writes the News app (docs/news/index.html)."""
    esc = html.escape
    cols = []
    for col in data["columns"]:
        cards = []
        for c in col["cards"]:
            city = c.get("city") or (c.get("town") if col["key"] in ("local", "pride") and c.get("town") != "Ozarks" else "")
            leb = (city or "").lower() == "lebanon"
            where = f' <span class="city{" leb" if leb else ""}">({esc(city)})</span>' if city else ""
            if col["key"] == "pride":  # Boss (2026-10-21): the town is already in the line ("Congrats to Waynesville's ...")
                where = ""
            sig = f'<div class="sig"><b>BUZZ:</b> {esc(c["signal"])}</div>' if c.get("signal") else ""
            joke = c.get("kind") == "joke"
            nolink = joke or col["key"] == "humor"  # Humor reads in one line; nothing to click
            punch = ""
            # On-air sentence replaces the headline. Jokes and roundups keep their own text.
            if joke:  # one line: Claude's tightened version, or setup and punchline joined
                main = esc(c.get("line") or f'{c["title"]} {c.get("punch", "")}'.strip())
            else:
                main = esc(c["line"]) if c.get("line") else esc(c["title"])
            cong = '<span class="tag cong">CONGRATS</span>' if c.get("congrats") else ""
            names = ""
            # LOCAL PRIDE (Boss 2026-10-19): "World Food Champs - names, from place, what/when/where."
            label = f'<span class="label">{esc(c["label"])}</span> &ndash; ' if c.get("label") else ""
            # The R-3 site gives no post dates, so its cards show a label instead of an age.
            if c.get("kind") == "event":
                tm = f' &middot; {esc(c["time"])}' if c.get("time") else ""
                head = (f'<div class="card" data-date="{c["date"]}"><div class="when"><span class="dl">{c["when_label"]}</span>{tm} '
                        f'<span class="src">&middot; {esc(c["source"])}</span></div>')
                names = (f'<div class="why">{esc(c["place"])}</div>' if c.get("place") else "") + \
                        (f'<div class="why">{esc(c["why"])}</div>' if c.get("why") else "")
            elif c.get("kind") == "concert":
                head = (f'<div class="card concert" data-date="{c["date"]}"><div class="when">CONCERT &middot; <span class="dl">{esc(c["when_label"])}</span> '
                        f'<span class="src">&middot; {esc(c["source"])}</span></div>')
            elif c.get("kind") == "day" and c.get("date"):
                # Boss (2026-10-21): jocks voice track a week ahead, so national days show the weekday they air.
                wd = date.fromisoformat(c["date"]).strftime("%A, %b %-d").upper()
                head = (f'<div class="card" data-date="{c["date"]}"><div class="when"><span class="dl">{wd}</span> '
                        f'<span class="src">&middot; {esc(c["title"])}</span></div>')
            elif c.get("source") == "Lebanon R-3 Schools":
                head = f'<div class="card"><div class="when">SCHOOL NEWS <span class="src">&middot; {esc(c["source"])}</span></div>'
            else:
                head = (f'<div class="card" data-ts="{ts_ms(c["ts"])}">'
                        f'<div class="when"><span>{static_when(c["ts"])}</span> <span class="src">&middot; {esc(c["source"])}</span></div>')
            cards.append(
                head +
                f'<div class="name">{cong}{label}{main}{where}</div>{names}{punch}{sig}' +
                ('</div>' if nolink else
                 f'<a class="link" href="{esc(c["url"])}" target="_blank" rel="noopener">'
                 f'{"Tickets / details" if c.get("kind") == "concert" else "Details" if c.get("kind") == "event" else "Read story"} &#8599;</a></div>'))
        body = "".join(cards) or '<div class="empty">Nothing worth airing today.</div>'
        if col["key"] == "music":
            body = ('<form class="search" onsubmit="return kjSearch();">'
                    '<input class="q" id="kjq" type="text" placeholder="Search artist or song">'
                    ' <input class="go" type="submit" value="Search"></form>'
                    f'<div class="results" id="kjres"></div><div id="kjcards">{body}</div>')
        sub = ""
        if col["key"] in data["lebanon"]:
            lb = data["lebanon"][col["key"]]
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
<title>{esc(doc_title)}</title><style>{CSS.replace("width:16.2%", f"width:{round(97 / max(1, len(cols)), 1)}%")}</style></head>
<body data-updated="{int(updated.timestamp() * 1000)}">
<div class="top"><div class="logo">103<span class="star">&#9733;</span>7 <span class="call">KJEL</span></div>
<div class="hd"><div class="title">{esc(title)}</div>
<div class="meta">{esc(doc_title)} &middot; updated {esc(stamp)}</div></div></div>
<div class="stale" id="stale">This report is more than a day old. The 6 AM refresh did not run.</div>
<div class="board">{"".join(cols)}</div>
<script>{SEARCH_JS}{JS}</script>
</body></html>
"""
    (ROOT / "docs").mkdir(exist_ok=True)
    for folder in (ROOT / "docs" / subdir, ROOT / subdir):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(page)
