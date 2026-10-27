"""Write the Buzz Report as one plain HTML file (no modern JS/CSS needed) -> docs/index.html and index.html.

Same look as the KJEL Event Board. Old browsers show every card from the HTML itself.
A tiny ES3 script turns timestamps into "5H AGO" and warns when the report is stale.
"""
import html
import json
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
.pc{background:#0A2A50;color:#FFFFFF;font-weight:bold;padding:0 3px;border-radius:3px}.pc.leb{background:#FDB913;color:#0A2A50}
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
.tag.keep{background:#FDB913;color:#0A2A50}.label{color:#D0101F;text-transform:uppercase}.nd .when{color:#0A2A50;font-size:13px}.ndn{color:#D0101F;font-weight:bold}.ndt{font-weight:normal}.card.concert{border-left:5px solid #D0101F}.tag.cong{background:#0A2A50;color:#FDB913}.tag.off{background:#D0101F;color:#FFFFFF}
.dsearch{margin:0;padding:12px 18px 2px}
.dsearch .dq{width:400px;max-width:60%;font-size:18px;padding:8px 10px;border:2px solid #FDB913;border-radius:8px}
.dsearch .dgo{font-size:17px;font-weight:bold;padding:8px 18px;border:0;border-radius:8px;background:#D0101F;color:#FFFFFF;cursor:pointer}
.dtabs{margin:0 0 8px}.dlab{color:#FFFFFF;font-weight:bold;font-size:16px;margin-right:10px}
.dsearch .dtab{font-size:16px;font-weight:bold;padding:7px 14px;margin-right:6px;border:2px solid #FFFFFF;border-radius:8px;background:#0A2A50;color:#FFFFFF;cursor:pointer}
.dsearch .dtab.on{background:#FDB913;border-color:#FDB913;color:#0A2A50}
.dhelp{color:#FFFFFF;font-size:15px;padding:6px 0 0}
.dsearch a{color:#FDB913;font-weight:bold;font-size:15px;margin-left:12px}
.col.kjh,.card.kjh{display:none}
.ctag{display:inline-block;background:#0A2A50;color:#FFFFFF;font-size:12px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;padding:1px 8px;border-radius:3px;margin-bottom:4px}
.ctag.leb{background:#FDB913;color:#0A2A50}
.dnote{color:#FFFFFF;font-size:16px;font-weight:bold;padding:6px 18px 0}
.dnote .dn{color:#FDB913}.dnote a{color:#FDB913}
.kjs .col{display:none}.kjs .col.kjm{display:inline-block}.kjs .card{display:none}.kjs .card.kjm{display:block}.kjs .search{display:none}
.wxw{border-left:6px solid #D0101F}.wxt{border-left:6px solid #FDB913}.wxi{border-left:6px solid #33445C}
.wxl{font-size:15px;font-weight:bold;margin:2px 0 6px}
.wxd{font-size:14px;margin:6px 0}.wxd .dl{font-weight:bold;color:#D0101F}
.wxok{font-size:13px;font-weight:bold;color:#33445C;padding:2px 4px 10px}
.wradd{display:block;width:100%;background:#D0101F;color:#FFFFFF;border:0;border-radius:8px;padding:9px;font-weight:bold;font-size:15px;cursor:pointer;margin-bottom:8px}
.wrt{white-space:pre-wrap;word-wrap:break-word}.wrh{font-weight:bold}.wrst{font-size:10px;color:#33445C;margin-right:4px}
.wwho{float:right;margin:1px 0 0 6px;white-space:nowrap}
.wwho b{display:inline-block;width:16px;height:16px;line-height:16px;text-align:center;font-size:11px;border:1px solid #8C97A8;border-radius:3px;color:#8C97A8;margin-left:2px;cursor:pointer}
.wwho b.on{background:#0A2A50;border-color:#0A2A50;color:#FDB913}
.wrtap{font-size:10px;color:#33445C;margin-top:3px;clear:both}
.wrmodal{display:none;position:fixed;left:0;top:0;right:0;bottom:0;background:rgba(0,0,0,.55);z-index:9}
.wrwin{background:#FFFFFF;border-radius:10px;max-width:560px;margin:6% auto 0;padding:14px;color:#0A2A50}
.wrmt{font-weight:bold;font-size:18px;margin-bottom:8px}
.wrwin textarea{width:100%;box-sizing:border-box;height:240px;font-size:15px;font-family:Arial,Helvetica,sans-serif;padding:8px;border:1px solid #C9CFD8;border-radius:6px}
.wrerr{color:#D0101F;font-size:13px;font-weight:bold;min-height:16px;margin-top:4px}
.wrrow{text-align:right;margin-top:8px}
.wrrow button{font-size:14px;padding:6px 16px;border-radius:6px;border:1px solid #C9CFD8;background:#FFFFFF;color:#0A2A50;cursor:pointer;margin-left:8px}
.wrrow .wrgo{background:#D0101F;border-color:#D0101F;color:#FFFFFF;font-weight:bold}
.wrfull{float:right;font-size:11px;font-weight:bold;margin:2px 6px 0 0;padding:1px 8px;border:1px solid #8C97A8;border-radius:10px;color:#0A2A50;text-decoration:none}
.wrby{font-size:15px;font-weight:bold;margin:0 0 8px}.wrby label{margin-right:14px;cursor:pointer}
.wrlock{margin:0 0 8px}.wrlock input{font-size:14px;padding:6px;border:1px solid #C9CFD8;border-radius:6px;width:120px}
.wrlock button{font-size:14px;padding:6px 12px;border:0;border-radius:6px;background:#0A2A50;color:#FFFFFF;cursor:pointer}
.wrlink{font-size:10px;color:#33445C}.wrmore{font-size:12px;font-weight:bold;padding:2px 4px 8px}.wrmore a{color:#0A2A50}
.wrtool{padding:12px 18px 0}.wrtool .wradd{display:inline-block;width:auto;padding:9px 22px;margin:0 12px 0 0;vertical-align:middle}
.wrtool .wrlock{display:inline-block;margin:0 12px 0 0;vertical-align:middle}.wrtool .wrlock button{background:#FDB913;color:#0A2A50;font-weight:bold}.wrtool .empty{display:inline-block;color:#FFFFFF;font-size:14px;vertical-align:middle}
.wrfp .col{max-height:calc(100vh - 140px);overflow-y:auto}
"""

# WireReady (Boss 2026-10-22): three news people paste wire stories and tap B, J or R when they use one. The page talks to
# the Google Apps Script in wireready/Code.gs (which keeps the stories and the log in a private Google Sheet and imports
# Missourinet daily). Two layouts: a compact column on News, and a full page with MOnet, Bruce, Jeff and Riley columns.
# ES3 plus XMLHttpRequest: no fetch, promises, arrow functions or let/const.
WR_ADD = '<button class="wradd" type="button" id="wradd">+ Add Story</button>'
WR_LOCK = ('<div class="wrlock" id="wrlock" style="display:none"><input type="password" id="wrpass" placeholder="Passcode"> '
           '<button type="button" id="wrunlock">Unlock</button></div>')
WR_MSG = '<div class="empty" id="wrmsg">Loading...</div>'
WR_TOOLBAR = f'<div class="wrtool">{WR_ADD}{WR_LOCK}{WR_MSG}</div>'
WR_MODAL = ('<div class="wrmodal" id="wrmodal"><div class="wrwin"><div class="wrmt">Add story</div>'
            '<div class="wrby">Entered by: <label><input type="radio" name="wrby" value="B"> B</label> '
            '<label><input type="radio" name="wrby" value="J"> J</label> '
            '<label><input type="radio" name="wrby" value="R"> R</label></div>'
            '<textarea id="wrtext" placeholder="Paste or type the story here"></textarea><div class="wrerr" id="wrerr"></div>'
            '<div class="wrrow"><button type="button" id="wrcancel">Cancel</button>'
            '<button type="button" class="wrgo" id="wrsubmit">Submit</button></div></div></div>')
WR_JS = r"""
(function(){
  var URL=__WR_URL__, WHO=['B','J','R'], MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var divs=document.getElementsByTagName('div'), lists=[], n;
  for(n=0;n<divs.length;n++){ if(divs[n].className==='wrlist') lists.push(divs[n]); }
  var msg=document.getElementById('wrmsg'), lock=document.getElementById('wrlock'), pass=document.getElementById('wrpass');
  var modal=document.getElementById('wrmodal'), ta=document.getElementById('wrtext'), err=document.getElementById('wrerr');
  var go=document.getElementById('wrsubmit'), unlock=document.getElementById('wrunlock'), busy=false;
  function getKey(){try{return window.localStorage.getItem('wrkey')||'';}catch(e){return '';}}
  function setKey(k){try{window.localStorage.setItem('wrkey',k);}catch(e){}}
  function longDate(s){var p=s.split('-');return MON[parseInt(p[1],10)-1]+' '+parseInt(p[2],10);}
  function shortDate(s){var p=s.split('-');return parseInt(p[1],10)+'/'+parseInt(p[2],10);}
  function say(t){msg.style.display=t?'block':'none';msg.innerHTML=t||'';}
  function needKey(t){lock.style.display='block';say(t);}
  function call(body,cb){
    var x=new XMLHttpRequest();
    x.open('POST',URL,true);
    x.setRequestHeader('Content-Type','text/plain;charset=utf-8');  // keeps the request "simple", so no CORS preflight
    x.onreadystatechange=function(){
      if(x.readyState!==4) return;
      var d=null; try{d=JSON.parse(x.responseText);}catch(e){}
      if(d && d.error==='passcode'){var had=getKey(); setKey(''); needKey(had?'That passcode did not work. Try again.':'Enter the passcode to open WireReady.');}
      cb(d);
    };
    body.key=getKey();
    x.send(JSON.stringify(body));
  }
  function tapper(id,who){
    return function(){call({action:'tap',id:id,who:who},function(d){
      if(d && d.ok) render(d.stories); else if(!d || d.error!=='passcode') say((d && d.error) || 'Could not reach WireReady. Try again.');});};
  }
  function card(s,showSrc){
    var c=document.createElement('div'), t=document.createElement('div'), who=document.createElement('span'), used=[], j;
    c.className='card'; t.className='wrt'; who.className='wwho';
    for(j=0;j<WHO.length;j++){
      var b=document.createElement('b'); b.innerHTML=WHO[j]; b.title='Tap when '+WHO[j]+' uses this story';
      if(s.taps[WHO[j]]){b.className='on'; used.push(WHO[j]+' '+shortDate(s.taps[WHO[j]]));}
      b.onclick=tapper(s.id,WHO[j]); who.appendChild(b);
    }
    var st=document.createElement('span'); st.className='wrst'; st.innerHTML='added '+longDate(s.added)+(showSrc?' &middot; '+s.by:'')+(s.kind==='summary'?' &middot; audio summary':'');
    t.appendChild(who); t.appendChild(st);
    var nl=s.text.indexOf('\n'), head=(s.by==='MOnet' || nl>0)?(nl>0?s.text.slice(0,nl):s.text):'';  // the title line is bold
    if(head){var h=document.createElement('span'); h.className='wrh'; h.appendChild(document.createTextNode(head)); t.appendChild(h); if(s.text.length>head.length) t.appendChild(document.createTextNode(s.text.slice(head.length)));}
    else t.appendChild(document.createTextNode(s.text));
    if(s.link){var a=document.createElement('a'); a.className='wrlink'; a.href=s.link; a.target='_blank'; a.rel='noopener'; a.innerHTML=' Missourinet &#8599;'; t.appendChild(a);}
    c.appendChild(t);
    if(used.length){var tp=document.createElement('div'); tp.className='wrtap'; tp.innerHTML=used.join(' &middot; '); c.appendChild(tp);}
    return c;
  }
  function render(stories){
    for(n=0;n<lists.length;n++){
      var L=lists[n], by=L.getAttribute('data-by'), lim=parseInt(L.getAttribute('data-limit')||'0',10), items=[], j;
      for(j=0;j<stories.length;j++){ if(by==='ALL' || stories[j].by===by) items.push(stories[j]); }
      var cnt=document.getElementById(L.getAttribute('data-count')); if(cnt) cnt.innerHTML=items.length;
      L.innerHTML='';
      var shown=(lim && items.length>lim)?lim:items.length;
      for(j=0;j<shown;j++) L.appendChild(card(items[j],by==='ALL'));
      if(shown<items.length){var m=document.createElement('div'); m.className='wrmore'; m.innerHTML='<a href="'+L.getAttribute('data-full')+'" target="_blank">+'+(items.length-shown)+' more on the full page</a>'; L.appendChild(m);}
      if(!items.length){var e=document.createElement('div'); e.className='empty'; e.innerHTML=(by==='ALL'?'No stories yet.':'Nothing here yet.'); L.appendChild(e);}
    }
  }
  function refresh(){
    if(busy || modal.style.display==='block') return;
    call({action:'list'},function(d){
      if(d && d.ok){lock.style.display='none'; say(''); render(d.stories);}
      else if(!d || d.error!=='passcode') say('Could not load WireReady. It will try again in a minute.');
    });
  }
  unlock.onclick=function(){
    var v=pass.value.replace(/^\s+|\s+$/g,''); if(!v) return;
    setKey(v); pass.value=''; say('Loading...'); refresh();
  };
  pass.onkeyup=function(ev){ev=ev||window.event; if((ev.keyCode||ev.which)===13) unlock.onclick();};
  document.getElementById('wradd').onclick=function(){
    var r=document.getElementsByName('wrby'), k;
    for(k=0;k<r.length;k++) r[k].checked=false;
    err.innerHTML=''; ta.value=''; modal.style.display='block'; ta.focus();
  };
  document.getElementById('wrcancel').onclick=function(){modal.style.display='none';};
  ta.onkeyup=function(){err.innerHTML='';};
  go.onclick=function(){
    var r=document.getElementsByName('wrby'), by='', k;
    for(k=0;k<r.length;k++){ if(r[k].checked) by=r[k].value; }
    var v=ta.value.replace(/^\s+|\s+$/g,'');
    if(!by){err.innerHTML='Check B, J or R: who is adding this story?';return;}
    if(!v){err.innerHTML='Paste or type the story first.';return;}
    if(busy) return;
    busy=true; go.innerHTML='Saving...';
    call({action:'add',text:v,by:by},function(d){
      busy=false; go.innerHTML='Submit';
      if(d && d.ok){modal.style.display='none'; render(d.stories);}
      else if(d && d.error==='passcode') err.innerHTML='The passcode was not accepted. Close this window and unlock again.';
      else err.innerHTML=(d && d.error) || 'Could not save. Check the connection and submit again.';
    });
  };
  refresh(); setInterval(refresh,60000);
})();
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

# Day / date search at the top of Show Prep (Boss 2026-10-21). A day name means that day THIS WEEK (Monday through Sunday);
# a date without a year means its next occurrence. It filters the board in place: cards with data-date equal to the
# target stay, everything else (including undated news cards) is hidden until Clear. ES3 only, like the rest.
# Boss (2026-10-23): "Search by:" has three choices so it is clear what the box means. Word = cards holding every word
# typed. One day = only cards dated that day. From a day on = every undated card stays and dated cards BEFORE the day
# hide (for voice tracking days ahead). The choice sets what the box means; Search runs it.
DAY_FORM = ('<form class="dsearch" onsubmit="return kjGo();">'
            '<div class="dtabs"><span class="dlab">Search by:</span>'
            '<input class="dtab on" id="kjt-word" type="button" value="Word" onclick="return kjMode(\'word\');">'
            '<input class="dtab" id="kjt-day" type="button" value="One day" onclick="return kjMode(\'day\');">'
            '<input class="dtab" id="kjt-from" type="button" value="From a day on" onclick="return kjMode(\'from\');"></div>'
            '<input class="dq" id="kjd" type="text" aria-label="Search" placeholder="Type a word, like Lebanon">'
            ' <input class="dgo" type="submit" value="Search"><a href="#" onclick="return kjDayClear();">Clear</a>'
            '<div class="dhelp" id="kjhelp">Shows every card that has the word.</div></form>'
            '<div class="dnote" id="kjdn"></div>')

DAY_JS = r"""
var KJ_DOW=['SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY'];
var KJ_DK={sun:0,sunday:0,mon:1,monday:1,tue:2,tues:2,tuesday:2,wed:3,weds:3,wednesday:3,thu:4,thur:4,thurs:4,thursday:4,fri:5,friday:5,sat:6,saturday:6};
var KJ_MO={jan:1,january:1,feb:2,february:2,mar:3,march:3,apr:4,april:4,may:5,jun:6,june:6,jul:7,july:7,aug:8,august:8,sep:9,sept:9,september:9,oct:10,october:10,nov:11,november:11,dec:12,december:12};
function kjHas(el,c){return (' '+el.className+' ').indexOf(' '+c+' ')>=0;}
function kjAdd(el,c){if(!kjHas(el,c)) el.className=el.className+' '+c;}
function kjDel(el,c){el.className=(' '+el.className+' ').replace(' '+c+' ',' ').replace(/^\s+|\s+$/g,'');}
function kjP2(n){return (n<10?'0':'')+n;}
function kjIso(y,m,d){return y+'-'+kjP2(m)+'-'+kjP2(d);}
function kjDayOf(y,m,d){var dt=new Date(y,m-1,d);return (dt.getFullYear()===y && dt.getMonth()===m-1 && dt.getDate()===d)?dt:null;}
function kjResolve(m,d,y,todayIso){
  var y0=new Date().getFullYear(), k, dt;
  if(y) return kjDayOf(y,m,d);
  for(k=0;k<5;k++){ dt=kjDayOf(y0+k,m,d); if(dt && kjIso(dt.getFullYear(),dt.getMonth()+1,dt.getDate())>=todayIso) return dt; }
  return null;
}
function kjTarget(raw){
  var s=raw.toLowerCase().replace(/,/g,' ').replace(/^\s+|\s+$/g,'').replace(/\s+/g,' ');
  var now=new Date(), todayIso=kjIso(now.getFullYear(),now.getMonth()+1,now.getDate()), parts, m, dt=null, wk=false, back, y;
  if(!s) return null;
  parts=s.split(' ');
  if(parts.length>1 && KJ_DK.hasOwnProperty(parts[0])){ parts.shift(); s=parts.join(' '); }  // "FRI, OCT 23" or "Fri 10/23"
  if(s==='today' || s==='tomorrow'){
    dt=new Date(now.getFullYear(),now.getMonth(),now.getDate()+(s==='tomorrow'?1:0));
  } else if(KJ_DK.hasOwnProperty(s)){
    back=(now.getDay()+6)%7;  // this week runs Monday through Sunday
    dt=new Date(now.getFullYear(),now.getMonth(),now.getDate()-back+(KJ_DK[s]+6)%7); wk=true;
  } else if((m=/^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(s))){
    dt=kjDayOf(parseInt(m[1],10),parseInt(m[2],10),parseInt(m[3],10));
  } else if((m=/^(\d{1,2})[\/\-.](\d{1,2})(?:[\/\-.](\d{2}|\d{4}))?$/.exec(s))){
    y=m[3]?parseInt(m[3],10):0; if(y && y<100) y+=2000;
    dt=kjResolve(parseInt(m[1],10),parseInt(m[2],10),y,todayIso);
  } else if((m=/^([a-z]+)\.? (\d{1,2})(?:st|nd|rd|th)?(?: (\d{4}))?$/.exec(s)) && KJ_MO.hasOwnProperty(m[1])){
    dt=kjResolve(KJ_MO[m[1]],parseInt(m[2],10),m[3]?parseInt(m[3],10):0,todayIso);
  }
  if(!dt) return null;
  return {dt:dt, iso:kjIso(dt.getFullYear(),dt.getMonth()+1,dt.getDate()), wk:wk, todayIso:todayIso, y0:now.getFullYear()};
}
function kjColOf(c){var col=c.parentNode; while(col && !kjHas(col,'col')) col=col.parentNode; return col;}
function kjBadge(col){var h=col.getElementsByTagName('h2')[0]; return h?h.getElementsByTagName('span')[0]:null;}
function kjDayReset(){
  var divs=document.getElementsByTagName('div'), i, c, sp;
  for(i=0;i<divs.length;i++){
    c=divs[i];
    if(kjHas(c,'kjm')) kjDel(c,'kjm');
    if(kjHas(c,'kjh')) kjDel(c,'kjh');
    if(kjHas(c,'col')){
      c.kjn=0; c.kjx=0; sp=kjBadge(c);
      if(sp && typeof sp.kjo!=='undefined') sp.innerHTML=sp.kjo;
    }
  }
  kjDel(document.body,'kjs');
}
function kjDayClear(){
  document.getElementById('kjd').value=''; document.getElementById('kjdn').innerHTML=''; kjDayReset(); return false;
}
// Search by: Word | One day | From a day on. The tab picks what the box means; Search runs it.
var KJ_MODE='word';
var KJ_HINT={word:'Type a word, like Lebanon', day:'Type a day or date, like Friday or 10/26', from:'Type a day or date, like Monday or 10/26'};
var KJ_HELP={word:'Shows every card that has the word.', day:'Shows only the cards dated that day.', from:'Hides cards dated before that day. Cards with no date stay.'};
function kjMode(m){
  var ids=['word','day','from'], i, b;
  KJ_MODE=m;
  for(i=0;i<ids.length;i++){ b=document.getElementById('kjt-'+ids[i]); if(ids[i]===m) kjAdd(b,'on'); else kjDel(b,'on'); }
  document.getElementById('kjd').placeholder=KJ_HINT[m];
  document.getElementById('kjhelp').innerHTML=KJ_HELP[m];
  document.getElementById('kjdn').innerHTML=''; kjDayReset();  // the old result no longer matches the choice
  if(/\S/.test(document.getElementById('kjd').value)) return kjGo();  // Boss (2026-10-23): text already typed, so clicking a choice runs the search
  return false;
}
function kjGo(){
  var v=document.getElementById('kjd').value, r;
  if(!/\S/.test(v)) return kjDayClear();
  kjDayReset();
  r=document.getElementById('kjres'); if(r && r.style.display==='block') kjClear();
  return KJ_MODE==='word' ? kjWords(v) : kjDay(v,KJ_MODE);
}
function kjDayGo(txt){document.getElementById('kjd').value=txt; return kjGo();}
function kjFilter(fn){  // keep the cards fn() accepts, hide the rest; a column with no kept card hides too
  var divs=document.getElementsByTagName('div'), i, c, col, sp, n=0, cols=0;
  for(i=0;i<divs.length;i++){
    c=divs[i];
    if(!kjHas(c,'card') || c.style.display==='none' || !fn(c)) continue;
    kjAdd(c,'kjm'); n++;
    col=kjColOf(c);
    if(col){ kjAdd(col,'kjm'); col.kjn=(col.kjn||0)+1; }
  }
  for(i=0;i<divs.length;i++){
    c=divs[i];
    if(kjHas(c,'col') && kjHas(c,'kjm')){
      cols++;
      if(!kjHas(c,'wx')){ sp=kjBadge(c); if(typeof sp.kjo==='undefined') sp.kjo=sp.innerHTML; sp.innerHTML=c.kjn; }  // the Wx badge counts alerts, so it keeps its own number
    }
  }
  kjAdd(document.body,'kjs');
  return {n:n, cols:cols};
}
function kjCardText(c){
  var s=c.textContent||c.innerText||'', as=c.getElementsByTagName('a'), i, a;
  for(i=0;i<as.length;i++){ a=as[i].textContent||as[i].innerText||''; if(a) s=s.replace(a,' '); }  // link labels ("Read story") are not story text
  return s.toLowerCase();
}
function kjWords(raw){  // cards holding EVERY word typed, in any order, anywhere in the card text
  var all=raw.toLowerCase().replace(/["“”]/g,' ').split(/\s+/), words=[], i, res;
  for(i=0;i<all.length;i++){ if(all[i]) words.push(all[i]); }
  if(!words.length) return kjDayClear();
  res=kjFilter(function(c){ var txt=kjCardText(c), j; for(j=0;j<words.length;j++){ if(txt.indexOf(words[j])<0) return false; } return true; });
  document.getElementById('kjdn').innerHTML='<span class="dn">&quot;'+kjEsc(words.join(' '))+'&quot;</span> &middot; '+res.n+(res.n===1?' card':' cards')+' in '+res.cols+(res.cols===1?' column':' columns')+'.'+(res.n?'':' Nothing on this page has all of those words.');
  return false;
}
function kjDay(v,mode){
  var from=(mode==='from'), note=document.getElementById('kjdn'), t, label, divs, i, k, m, d, c, col, sp, cards, n=0, nx, res;
  t=kjTarget(v);
  if(!t){ note.innerHTML='Not a day or date. Try Friday or 10/26.'; return false; }
  label=KJ_DOW[t.dt.getDay()]+' '+(t.dt.getMonth()+1)+'/'+t.dt.getDate()+(t.dt.getFullYear()!==t.y0?'/'+t.dt.getFullYear():'');
  if(t.iso<t.todayIso){
    note.innerHTML='<span class="dn">'+label+'</span> has passed.';
    if(t.wk){ nx=new Date(t.dt.getFullYear(),t.dt.getMonth(),t.dt.getDate()+7);
      note.innerHTML='<span class="dn">'+label+'</span> has passed this week. <a href="#" onclick="return kjDayGo(\''+(nx.getMonth()+1)+'/'+nx.getDate()+'\');">Show '+KJ_DOW[nx.getDay()].substr(0,3)+' '+(nx.getMonth()+1)+'/'+nx.getDate()+'</a>'; }
    return false;
  }
  divs=document.getElementsByTagName('div');
  if(from){
    // Undated cards stay. Dated cards before the date hide, and a column left with no cards goes too. Hiding instead of
    // showing leaves anything the page adds later (live weather alerts) alone.
    for(i=0;i<divs.length;i++){
      c=divs[i];
      if(!kjHas(c,'card') || c.style.display==='none') continue;
      d=c.getAttribute('data-date');
      if(d && d<t.iso){ kjAdd(c,'kjh'); n++; col=kjColOf(c); if(col) col.kjx=1; }
    }
    for(i=0;i<divs.length;i++){
      c=divs[i];
      if(!kjHas(c,'col') || !c.kjx) continue;
      cards=c.getElementsByTagName('div'); m=0;
      for(k=0;k<cards.length;k++){ if(kjHas(cards[k],'card') && !kjHas(cards[k],'kjh') && cards[k].style.display!=='none') m++; }
      sp=kjBadge(c); if(sp){ if(typeof sp.kjo==='undefined') sp.kjo=sp.innerHTML; sp.innerHTML=m; }
      if(!m) kjAdd(c,'kjh');
    }
    note.innerHTML='<span class="dn">FROM '+label+(t.wk?' (this week)':'')+' on</span> &middot; cards with no date stay. '+n+(n===1?' earlier card':' earlier cards')+' hidden.';
    return false;
  }
  res=kjFilter(function(c){ return c.getAttribute('data-date')===t.iso; });
  note.innerHTML='<span class="dn">'+label+(t.wk?' (this week)':'')+'</span> &middot; '+res.n+(res.n===1?' card':' cards')+' in '+res.cols+(res.cols===1?' column':' columns')+'. Cards with no date are hidden.';
  return false;
}
"""

# Wx column (Boss 2026-10-21): the build writes a snapshot; this re-reads active alerts from the National Weather Service
# on load and every 5 minutes, so a warning issued after the 6 AM build still shows. KJ_WXC (county table) comes from wx.py.
WX_JS = r"""
function kjWxIso(s){
  var m=/^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(Z|([+-])(\d\d):(\d\d))$/.exec(s||'');
  if(!m) return null;
  var ms=Date.UTC(parseInt(m[1],10),parseInt(m[2],10)-1,parseInt(m[3],10),parseInt(m[4],10),parseInt(m[5],10),parseInt(m[6],10));
  if(m[7]!=='Z') ms-=(m[8]==='-'?-1:1)*(parseInt(m[9],10)*60+parseInt(m[10],10))*60000;
  return ms;
}
function kjWxClock(d){var h=d.getHours(), mi=d.getMinutes(); return (h%12===0?12:h%12)+(mi?':'+(mi<10?'0':'')+mi:'')+' '+(h>=12?'PM':'AM');}
function kjWxTime(ms){  // "7 PM (Thu 10/22)": the date always follows the time
  var d=new Date(ms);
  return kjWxClock(d)+' ('+['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d.getDay()]+' '+(d.getMonth()+1)+'/'+d.getDate()+')';
}
function kjWxCovers(hit){  // "Camden county (Camdenton, Osage Beach, Lake Ozark); Laclede county (Lebanon)"
  var out=[], i;
  if(hit.length===KJ_WXC.length) return 'entire listening area';
  for(i=0;i<hit.length;i++) out.push(kjEsc(hit[i].n)+' county'+(hit[i].t.length?' ('+kjEsc(hit[i].t.join(', '))+')':''));
  return out.join('; ');
}
function kjWxCard(p,hit){
  var ev=p.event||'Alert', cls=/Warning$/.test(ev)?'wxw':'wxt', ms=kjWxIso(p.ends||p.expires), ll=hit[0].ll.split(',');
  return '<div class="card '+cls+'"><div class="name"><span class="label">'+kjEsc(ev)+':</span> '+kjWxCovers(hit)+(ms?' until '+kjWxTime(ms):'')+'</div>'
    +'<a class="link" href="https://forecast.weather.gov/MapClick.php?lat='+ll[0]+'&amp;lon='+ll[1]+'" target="_blank" rel="noopener">NWS details &#8599;</a></div>';
}
function kjWxLive(){
  var x;
  if(!window.JSON || !window.XMLHttpRequest) return;
  try{ x=new XMLHttpRequest(); x.open('GET','https://api.weather.gov/alerts/active?status=actual&area=MO',true); x.setRequestHeader('Accept','application/geo+json'); }catch(e){ return; }
  x.onreadystatechange=function(){
    if(x.readyState!==4 || x.status!==200) return;
    var f, buckets=[[],[]], i, j, k, p, same, hit, r, n=0, out='';
    try{ f=JSON.parse(x.responseText).features||[]; }catch(e){ return; }
    for(i=0;i<f.length;i++){
      p=f[i].properties; if(!p || p.status!=='Actual' || !/(Warning|Watch)$/.test(p.event||'')) continue;  // severe only: watches and warnings
      same=(p.geocode && p.geocode.SAME) || []; hit=[];
      for(j=0;j<KJ_WXC.length;j++){ for(k=0;k<same.length;k++){ if(same[k]===KJ_WXC[j].s){ hit.push(KJ_WXC[j]); break; } } }
      if(!hit.length) continue;
      r=/Warning$/.test(p.event)?0:1;
      buckets[r].push(kjWxCard(p,hit)); n++;
    }
    out=buckets[0].concat(buckets[1]).join('');
    document.getElementById('wxalerts').innerHTML=out||'<div class="wxok">No watches or warnings.</div>';
    document.getElementById('wxcount').innerHTML=n;
    document.getElementById('wxstamp').innerHTML='Alerts live &middot; '+kjWxClock(new Date());
  };
  try{ x.send(null); }catch(e){}
}
kjWxLive(); setInterval(kjWxLive,300000);
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
    var nd=e.className.indexOf(' nd')>=0;  // Nat'l Day cards lead with the weekday, so the flag goes after it
    if(dd===today){ if(dl) dl.innerHTML=nd?dl.innerHTML+' &middot; TODAY':'TODAY &middot; '+dl.innerHTML; e.className=e.className+' new'; }
    else if(dd===tmr && dl){ dl.innerHTML=nd?dl.innerHTML+' &middot; TOMORROW':'TOMORROW &middot; '+dl.innerHTML; }
  }
  var u=parseInt(document.body.getAttribute('data-updated'),10);
  if(u && now-u>30*3600000){var s=document.getElementById('stale'); if(s) s.style.display='block';}
})();
"""


def ts_ms(iso):
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def static_when(iso):
    return datetime.fromisoformat(iso).astimezone(CT).strftime("%a %b %-d").upper()


# City name colors for the Holiday Events chips (Boss 2026-10-27). Lebanon is always the station gold; the others keep one color each
# so a city is easy to spot down the list. Towns not listed get a color from their name, the same every day.
CITY_COLORS = {"waynesville": "#0A2A50", "saint robert": "#B3121F", "st. robert": "#B3121F", "fort leonard wood": "#8C2F5A",
               "marshfield": "#1B6E3C", "osage beach": "#0B7285", "lake ozark": "#2F5DA8", "camdenton": "#6B3FA0",
               "eldon": "#A24E00", "bolivar": "#4D5B2E", "buffalo": "#7A4A21", "richland": "#B0451E", "dixon": "#A12D6D",
               "crocker": "#5C5C5C", "laurie": "#8A5A00", "hermitage": "#2E6F95", "hartville": "#7B2D26"}
CITY_FALLBACK = ["#0A2A50", "#B3121F", "#1B6E3C", "#6B3FA0", "#A24E00", "#0B7285", "#8C2F5A", "#4D5B2E", "#2F5DA8", "#7A4A21"]


def city_color(town):
    key = town.strip().lower()
    return CITY_COLORS.get(key) or CITY_FALLBACK[sum(ord(ch) for ch in key) % len(CITY_FALLBACK)]


def write(data, title="The Buzz", doc_title="KJEL Buzz Report", subdir="", day_search=False):
    """subdir="" writes the Buzz (docs/index.html); subdir="news" writes the News app (docs/news/index.html).
    day_search=True adds the day / date search bar (Show Prep)."""
    esc = html.escape
    cols = []
    wx_conf = ""
    wr_url = ""
    for col in data["columns"]:
        if col.get("wireready_url"):  # WireReady draws itself in the browser from the Google Apps Script
            wr_url = col["wireready_url"]
            wr = col["wr"]  # {"by": "ALL" | "MOnet" | "B" | "J" | "R", "limit": n, "full": link to the full page}
            cid = "wrc-" + col["key"]
            if wr["by"] == "ALL":  # the compact column on News: controls live in the column, newest few stories, link to the full page
                cols.append(f'<div class="col wr"><h2>{esc(col["name"])} <span class="count" id="{cid}">0</span>'
                            f'<a class="wrfull" href="{wr["full"]}" target="_blank">Full page &#8599;</a></h2>'
                            f'{WR_ADD}{WR_LOCK}{WR_MSG}<div class="wrlist" data-by="ALL" data-limit="{wr["limit"]}" '
                            f'data-count="{cid}" data-full="{wr["full"]}"></div></div>')
            else:  # one column of the full page
                cols.append(f'<div class="col wr"><h2>{esc(col["name"])} <span class="count" id="{cid}">0</span></h2>'
                            f'<div class="wrlist" data-by="{wr["by"]}" data-count="{cid}"></div></div>')
            continue
        if col.get("html"):  # a column that renders itself (Wx); its badge counts active alerts
            wx_conf = col["conf"]
            cols.append(f'<div class="col wx"><h2>{esc(col["name"])} <span class="count" id="wxcount">{col["count"]}</span></h2>{col["html"]}</div>')
            continue
        cards, towns = [], []
        for c in col["cards"]:
            towns.append(c.get("city") or "")
            # Boss (2026-10-23): the place goes inside the quick-read line, so no card shows "(Town)" after it any more.
            where = ""
            sig = f'<div class="sig"><b>BUZZ:</b> {esc(c["signal"])}</div>' if c.get("signal") else ""
            joke = c.get("kind") == "joke"
            nolink = joke or col["key"] == "humor" or (c.get("kind") == "event" and not c.get("url"))  # Humor reads in one line; hand-entered events may have no link
            punch = ""
            # On-air sentence replaces the headline. Jokes and roundups keep their own text.
            if joke:  # one line: Claude's tightened version, or setup and punchline joined
                main = esc(c.get("line") or f'{c["title"]} {c.get("punch", "")}'.strip())
            else:
                main = esc(c["line"]) if c.get("line") else esc(c["title"])
            if col["key"] == "pride":  # Boss (2026-10-23): LOCAL PRIDE highlights its city wherever the line names it (Lebanon gold, other towns navy)
                town = c.get("city") or c.get("town") or ""
                if town:
                    main = main.replace(esc(town), f'<span class="pc{" leb" if town.lower() == "lebanon" else ""}">{esc(town)}</span>')
            cong = '<span class="tag cong">CONGRATS</span>' if c.get("congrats") else ""
            names = ""
            # LOCAL PRIDE (Boss 2026-10-19): "World Food Champs - names, from place, what/when/where."
            label = f'<span class="label">{esc(c["label"])}</span> &ndash; ' if c.get("label") else ""
            # The R-3 site gives no post dates, so its cards show a label instead of an age.
            if c.get("kind") == "event":
                tm = f' &middot; {esc(c["time"])}' if c.get("time") else ""
                # Boss (2026-10-27): Holiday Events run in date order, each card led by its city name in color.
                ct = ""
                if col.get("city_tags") and c.get("city"):
                    town = c["city"]
                    ct = (f'<div class="ctag leb">{esc(town)}</div>' if town.lower() == "lebanon"
                          else f'<div class="ctag" style="background:{city_color(town)}">{esc(town)}</div>')
                head = (f'<div class="card" data-date="{c["date"]}" data-min="{c.get("min", 0)}">{ct}<div class="when"><span class="dl">{c["when_label"]}</span>{tm} '
                        f'<span class="src">&middot; {esc(c["source"])}</span></div>')
                names = (f'<div class="why">{esc(c["place"])}</div>' if c.get("place") else "") + \
                        (f'<div class="why">{esc(c["why"])}</div>' if c.get("why") else "")
            elif c.get("kind") == "timely":  # Timely: a dated talking point; the date label turns into TODAY / TOMORROW in the browser
                head = (f'<div class="card" data-date="{c["date"]}"><div class="when"><span class="dl">{esc(c["when_label"])}</span> '
                        f'<span class="src">&middot; {esc(c["source"])}</span></div>')
            elif c.get("kind") == "concert":
                head = (f'<div class="card concert" data-date="{c["date"]}"><div class="when">CONCERT &middot; <span class="dl">{esc(c["when_label"])}</span> '
                        f'<span class="src">&middot; {esc(c["source"])}</span></div>')
            elif c.get("kind") == "day" and c.get("date"):
                # Boss (2026-10-21): "Nat'l Day" cards = WEEKDAY 10/22, the day's name in bold color, then one
                # entertaining sentence in plain text. Jocks voice track a week ahead, so the weekday leads.
                d = date.fromisoformat(c["date"])
                head = (f'<div class="card nd" data-date="{c["date"]}"><div class="when">'
                        f'<span class="dl">{d.strftime("%A").upper()} {d.month}/{d.day}</span></div>')
                label = ""
                # Boss (2026-10-21): the title is the day's exact name ("National Bubble Blowing Day"), never shortened.
                main = f'<span class="ndn">{esc(c["title"].strip())}</span> <span class="ndt">{esc(c.get("line", ""))}</span>'
            elif c.get("source") == "Lebanon R-3 Schools":
                head = f'<div class="card"><div class="when">SCHOOL NEWS <span class="src">&middot; {esc(c["source"])}</span></div>'
            else:
                head = (f'<div class="card" data-ts="{ts_ms(c["ts"])}">'
                        f'<div class="when"><span>{static_when(c["ts"])}</span> <span class="src">&middot; {esc(c["source"])}</span></div>')
            cards.append(
                head +
                f'<div class="name">{cong}{label}{main}{where}</div>{names}{punch}{"" if c.get("kind") == "day" else sig}' +
                ('</div>' if nolink else
                 f'<a class="link" href="{esc(c["url"])}" target="_blank" rel="noopener">'
                 f'{"Tickets / details" if c.get("kind") == "concert" else "Details" if c.get("kind") == "event" else "Source" if c.get("kind") == "timely" else "Read story"} &#8599;</a></div>'))
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
{DAY_FORM if day_search else ""}
{WR_TOOLBAR if data.get("wr_toolbar") else ""}
<div class="board{" wrfp" if data.get("wr_toolbar") else ""}">{"".join(cols)}</div>
{WR_MODAL if wr_url else ""}
<script>{SEARCH_JS}{DAY_JS if day_search else ""}{f"var KJ_WXC={wx_conf};" + WX_JS if wx_conf else ""}{JS}{WR_JS.replace("__WR_URL__", json.dumps(wr_url)) if wr_url else ""}</script>
</body></html>
"""
    (ROOT / "docs").mkdir(exist_ok=True)
    for folder in (ROOT / "docs" / subdir, ROOT / subdir):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(page)
