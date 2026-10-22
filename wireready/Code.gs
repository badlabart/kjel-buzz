/**
 * WireReady backend (Boss 2026-10-22). A Google Apps Script web app bound to a private Google Sheet.
 *
 * Sheet "Stories": id | added | text | by | link
 *     by = "MOnet" (imported daily from the Missourinet feed) or B / J / R (typed in by that person)
 * Sheet "Taps":    tapped | who | story added | story text | story id | story from
 *     the LOG: one row each time B, J or R taps a story, in date order. Tapping again undoes it.
 *
 * The News page and the WireReady full page (kjel-news) call this over POST. Every call carries the shared PASSCODE.
 * Daily, importMonet() adds new Missourinet stories. Weekly, weeklyLog() emails the last 7 days of the Taps log to REPORT_TO.
 *
 * Script properties, set from the WireReady menu in the Sheet (never in code or the repo):
 *   PASSCODE   the shared passcode the three news people type once per browser
 *   REPORT_TO  who gets the weekly email
 *
 * @OnlyCurrentDoc  (the script may touch this one Sheet only, not the rest of the Drive)
 */
var TZ = 'America/Chicago';
var WHO = ['B', 'J', 'R'];
var KEEP_DAYS = 14;      // stories older than this drop off the page (they stay in the Sheet and the log)
var MAX_TEXT = 20000;
var FEED = 'https://www.missourinet.com/feed/';
// Missourinet's firewall refuses the default Apps Script user agent, so the feed is asked for like a browser.
var BROWSER_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';

function prop_(k) { return PropertiesService.getScriptProperties().getProperty(k); }
function ymd_(d) { return Utilities.formatDate(d, TZ, 'yyyy-MM-dd'); }
function daysAgo_(n) { return new Date(new Date().getTime() - n * 86400000); }
function dstr_(v) { return v instanceof Date ? ymd_(v) : String(v); }

var HEADERS = {
  Stories: ['id', 'added', 'text', 'by', 'link'],
  Taps: ['tapped', 'who', 'story added', 'story text', 'story id', 'story from']
};

function sheet_(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.appendRow(HEADERS[name]);
    sh.setFrozenRows(1);
    sh.getRange('A:F').setNumberFormat('@');  // plain text, so dates and "=..." story text stay as typed
  }
  return sh;
}
// appendRow can turn "=..." or date-like text into formulas or dates. Formatting the new row as plain text first
// keeps every cell exactly as typed.
function appendText_(sh, vals) {
  var rg = sh.getRange(sh.getLastRow() + 1, 1, 1, vals.length);
  rg.setNumberFormat('@');
  rg.setValues([vals]);
}
function stories_() { return sheet_('Stories'); }
function taps_() { return sheet_('Taps'); }

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function doGet() { return json_({ ok: true, app: 'WireReady' }); }

function doPost(e) {
  var out;
  try {
    var p = JSON.parse(e.postData.contents);
    var pass = prop_('PASSCODE');
    if (!pass || String(p.key) !== pass) return json_({ ok: false, error: 'passcode' });
    if (p.action === 'add' || p.action === 'tap') {
      var lock = LockService.getScriptLock();
      lock.waitLock(10000);
      try {
        if (p.action === 'add') add_(p.text, p.by); else tap_(p.id, p.who);
      } finally { lock.releaseLock(); }
    }
    out = { ok: true, stories: list_() };
  } catch (err) {
    out = { ok: false, error: String(err && err.message || err) };
  }
  return json_(out);
}

function add_(text, by) {
  if (WHO.indexOf(by) < 0) throw new Error('Check B, J or R to say who is adding the story');
  text = String(text || '').replace(/^\s+|\s+$/g, '');
  if (!text) throw new Error('The story is empty');
  if (text.length > MAX_TEXT) throw new Error('The story is too long');
  appendText_(stories_(), [Utilities.getUuid().substring(0, 8),
                           Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm'), text, by, '']);
}

function tap_(id, who) {
  if (WHO.indexOf(who) < 0) throw new Error('Unknown initial');
  var st = stories_().getDataRange().getValues(), story = null, i;
  for (i = 1; i < st.length; i++) { if (String(st[i][0]) === String(id)) { story = st[i]; break; } }
  if (!story) throw new Error('Story not found');
  var sh = taps_(), rows = sh.getDataRange().getValues();
  for (i = rows.length - 1; i >= 1; i--) {
    if (String(rows[i][4]) === String(id) && String(rows[i][1]) === who) { sh.deleteRow(i + 1); return; }  // tap again = undo
  }
  appendText_(sh, [ymd_(new Date()), who, dstr_(story[1]).slice(0, 10), String(story[2]), String(id), String(story[3] || 'MOnet')]);
}

function list_() {
  var cutoff = ymd_(daysAgo_(KEEP_DAYS)), taps = {}, out = [];
  taps_().getDataRange().getValues().slice(1).forEach(function (r) {
    var id = String(r[4]);
    if (!taps[id]) taps[id] = {};
    taps[id][String(r[1])] = dstr_(r[0]).slice(0, 10);
  });
  stories_().getDataRange().getValues().slice(1).forEach(function (r) {
    var added = dstr_(r[1]).slice(0, 10);
    if (!r[0] || added < cutoff) return;
    out.push({ id: String(r[0]), added: added, text: String(r[2]), by: String(r[3] || 'MOnet'), link: String(r[4] || ''),
               taps: taps[String(r[0])] || {} });
  });
  out.reverse();  // newest first
  return out;
}

// ---- Missourinet import (daily) -------------------------------------------------------------------------------

function decode_(s) {
  var named = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', hellip: '...', ndash: '-', mdash: '-',
                lsquo: "'", rsquo: "'", ldquo: '"', rdquo: '"' };
  return String(s).replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, function (m, g) {
    if (g.charAt(0) === '#') {
      var n = g.charAt(1).toLowerCase() === 'x' ? parseInt(g.slice(2), 16) : parseInt(g.slice(1), 10);
      return n === 8217 || n === 8216 ? "'" : n === 8220 || n === 8221 ? '"' : n === 8211 || n === 8212 ? '-' : String.fromCharCode(n);
    }
    return named.hasOwnProperty(g.toLowerCase()) ? named[g.toLowerCase()] : m;
  });
}

function htmlToText_(h) {
  h = String(h).replace(/^\s*<!\[CDATA\[/, '').replace(/\]\]>\s*$/, '');
  h = h.replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ').replace(/<\/p>|<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, ' ');
  h = decode_(h).replace(/[ \t ]+/g, ' ').replace(/ *\n */g, '\n').replace(/\n{3,}/g, '\n\n');
  return h.replace(/^\s+|\s+$/g, '');
}

function parseFeed_(xml) {
  var items = [], re = /<item>([\s\S]*?)<\/item>/g, m;
  function tag(s, t) { var x = new RegExp('<' + t + '[^>]*>([\\s\\S]*?)</' + t + '>').exec(s); return x ? x[1] : ''; }
  while ((m = re.exec(xml))) {
    var title = htmlToText_(tag(m[1], 'title')), link = htmlToText_(tag(m[1], 'link')), pub = new Date(htmlToText_(tag(m[1], 'pubDate')));
    var body = htmlToText_(tag(m[1], 'description')).replace(/\s*The post .* appeared first on .*$/, '');
    if (title && link && !isNaN(pub.getTime())) items.push({ title: title, link: link, pub: pub, excerpt: body });
  }
  return items;
}

function fetchFeed_() {
  var r = UrlFetchApp.fetch(FEED, { muteHttpExceptions: true, followRedirects: true,
                                    headers: { 'User-Agent': BROWSER_UA, 'Accept-Language': 'en-US,en;q=0.9' } });
  if (r.getResponseCode() !== 200) throw new Error('Missourinet answered HTTP ' + r.getResponseCode());
  return r.getContentText();
}

// Adds every Missourinet story not already in the Stories tab (matched by link). Returns how many were added.
function importMonet() {
  var items = parseFeed_(fetchFeed_());
  if (!items.length) throw new Error('The Missourinet feed had no stories');
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var sh = stories_(), have = {};
    sh.getDataRange().getValues().slice(1).forEach(function (r) { if (r[4]) have[String(r[4])] = true; });
    var fresh = items.filter(function (it) { return !have[it.link]; });
    fresh.sort(function (a, b) { return a.pub.getTime() - b.pub.getTime(); });  // oldest first, so the newest ends up on top
    fresh.forEach(function (it) {
      appendText_(sh, [Utilities.getUuid().substring(0, 8), Utilities.formatDate(it.pub, TZ, 'yyyy-MM-dd HH:mm'),
                       it.title + (it.excerpt ? '\n' + it.excerpt : ''), 'MOnet', it.link]);
    });
    return fresh.length;
  } finally { lock.releaseLock(); }
}

// ---- weekly email -------------------------------------------------------------------------------------------

function label_(s) {  // "2026-10-14" -> "Wed Oct 14"
  var p = s.split('-');
  return Utilities.formatDate(new Date(Date.UTC(+p[0], +p[1] - 1, +p[2], 12)), TZ, 'EEE MMM d');
}
function esc_(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

function weeklyLog() {
  var to = prop_('REPORT_TO');
  if (!to) throw new Error('Set the REPORT_TO script property first');
  var from = ymd_(daysAgo_(7)), through = ymd_(daysAgo_(1));  // Monday run = the Monday-to-Sunday that just ended
  var rows = taps_().getDataRange().getValues().slice(1).map(function (r) {
    return { tapped: dstr_(r[0]).slice(0, 10), who: String(r[1]), added: dstr_(r[2]).slice(0, 10), text: String(r[3]),
             id: String(r[4]), from: String(r[5] || 'MOnet') };
  }).filter(function (r) { return r.tapped >= from && r.tapped <= through; });
  rows.sort(function (a, b) { return a.tapped < b.tapped ? -1 : a.tapped > b.tapped ? 1 : 0; });

  var groups = [], byKey = {};  // one entry per day per story, listing who used it that day
  rows.forEach(function (r) {
    var k = r.tapped + '|' + r.id;
    if (!byKey[k]) { byKey[k] = { tapped: r.tapped, added: r.added, text: r.text, from: r.from, who: [] }; groups.push(byKey[k]); }
    byKey[k].who.push(r.who);
  });

  var subject = 'WireReady log: ' + label_(from) + ' to ' + label_(through);
  var plain = [], html = [];
  if (!groups.length) {
    plain.push('No stories were marked used from ' + label_(from) + ' to ' + label_(through) + '.');
    html.push('<p>No stories were marked used from ' + label_(from) + ' to ' + label_(through) + '.</p>');
  }
  var day = '';
  groups.forEach(function (g) {
    if (g.tapped !== day) {
      day = g.tapped;
      plain.push('', '== ' + label_(day).toUpperCase() + ' ==');
      html.push('<h3 style="margin:18px 0 4px">' + label_(day) + '</h3>');
    }
    var src = g.from === 'MOnet' ? 'from Missourinet' : 'entered by ' + g.from;
    var head = g.who.join(', ') + ' used a story (' + src + ', added ' + label_(g.added).replace(/^\w+ /, '') + ')';
    plain.push('', head, g.text);
    html.push('<p style="margin:10px 0 2px"><b>' + esc_(head) + '</b></p>' +
              '<div style="white-space:pre-wrap;margin:0 0 6px">' + esc_(g.text) + '</div>');
  });
  MailApp.sendEmail({ to: to, subject: subject, body: plain.join('\n'),
                      htmlBody: '<div style="font-family:Arial,sans-serif;font-size:14px">' + html.join('') + '</div>',
                      name: 'WireReady' });
}

// Run once from the editor (Run > installTriggers): Missourinet import every day around 4 AM Central, and the
// log email every Monday around 6 AM Central.
function installTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    var f = t.getHandlerFunction();
    if (f === 'weeklyLog' || f === 'importMonet') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('importMonet').timeBased().everyDays(1).atHour(4).create();
  ScriptApp.newTrigger('weeklyLog').timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(6).create();
}

// ---- WireReady menu in the Sheet (so the passcode and email address never sit in code or chat) -------------------

function onOpen() {
  SpreadsheetApp.getUi().createMenu('WireReady')
    .addItem('Set passcode', 'setPasscode')
    .addItem('Set weekly email address', 'setReportTo')
    .addItem('Import Missourinet stories now', 'importMonetNow')
    .addItem('Send last week\'s log now', 'weeklyLog')
    .addToUi();
}

function ask_(title, prompt, key) {
  var ui = SpreadsheetApp.getUi();
  var r = ui.prompt(title, prompt, ui.ButtonSet.OK_CANCEL);
  if (r.getSelectedButton() !== ui.Button.OK) return false;
  var v = r.getResponseText().replace(/^\s+|\s+$/g, '');
  if (!v) { ui.alert('Nothing was entered, so nothing was saved.'); return false; }
  PropertiesService.getScriptProperties().setProperty(key, v);
  ui.alert('Saved.');
  return true;
}
function setPasscode() { return ask_('WireReady passcode', 'Type the shared passcode the news people will use.', 'PASSCODE'); }
function setReportTo() { return ask_('Weekly email address', 'Who should get the weekly WireReady log?', 'REPORT_TO'); }

function importMonetNow() {
  var ui = SpreadsheetApp.getUi();
  try { ui.alert(importMonet() + ' new Missourinet stories added.'); }
  catch (e) { ui.alert('Could not import: ' + e.message); }
}

// Run once from the editor to create the two sheets, or to bring their header rows up to date.
function setup() {
  stories_(); taps_();
  Object.keys(HEADERS).forEach(function (n) {
    var h = HEADERS[n];
    sheet_(n).getRange(1, 1, 1, h.length).setValues([h]);
  });
}

// Run from the editor after setup: adds two test stories, taps B, undoes it, checks "=..." text stays text,
// removes its own rows, and logs PASSED or FAILED in the Execution log.
function selfTest() {
  var before = list_().length;
  add_('=1+1', 'B');
  add_('SELF TEST story, safe to ignore', 'J');
  var s = list_()[0], f = list_()[1];
  tap_(s.id, 'B');
  var tapped = list_()[0].taps.B === ymd_(new Date());
  tap_(s.id, 'B');
  var undone = !list_()[0].taps.B;
  var textKept = f.text === '=1+1' && f.by === 'B' && s.by === 'J';
  var sh = stories_(), rows = sh.getDataRange().getValues();
  for (var i = rows.length - 1; i >= 1; i--) {
    if (String(rows[i][0]) === s.id || String(rows[i][0]) === f.id) sh.deleteRow(i + 1);
  }
  var ok = tapped && undone && textKept && list_().length === before;
  Logger.log('SELF TEST ' + (ok ? 'PASSED' : 'FAILED') + ' (tapped=' + tapped + ', undone=' + undone + ', textKept=' + textKept +
             ', saw ' + JSON.stringify([f.text, f.by, s.by]) + ')');
  return ok;
}
