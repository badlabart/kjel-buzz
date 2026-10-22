/**
 * WireReady backend (Boss 2026-10-22). A Google Apps Script web app bound to a private Google Sheet.
 *
 * Sheet "Stories": id | added | text            every pasted story
 * Sheet "Taps":    tapped | who | story added | story text | story id
 *                  the LOG: one row each time B, J or R taps a story, in date order. Tapping again undoes it.
 *
 * The News page (kjel-news) calls this over POST. Every call carries the shared PASSCODE.
 * Once a week, weeklyLog() emails the last 7 days of the Taps log to REPORT_TO.
 *
 * Script properties (Project Settings > Script properties), set by hand, never in the repo:
 *   PASSCODE   the shared passcode the three news people type once per browser
 *   REPORT_TO  who gets the weekly email
 */
var TZ = 'America/Chicago';
var WHO = ['B', 'J', 'R'];
var KEEP_DAYS = 14;      // stories older than this drop off the page (they stay in the Sheet and the log)
var MAX_TEXT = 20000;

function prop_(k) { return PropertiesService.getScriptProperties().getProperty(k); }
function ymd_(d) { return Utilities.formatDate(d, TZ, 'yyyy-MM-dd'); }
function daysAgo_(n) { return new Date(new Date().getTime() - n * 86400000); }
function dstr_(v) { return v instanceof Date ? ymd_(v) : String(v); }

function sheet_(name, header) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.appendRow(header);
    sh.setFrozenRows(1);
    sh.getRange('A:E').setNumberFormat('@');  // plain text, so dates and "=..." story text stay as typed
  }
  return sh;
}
function stories_() { return sheet_('Stories', ['id', 'added', 'text']); }
function taps_() { return sheet_('Taps', ['tapped', 'who', 'story added', 'story text', 'story id']); }

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
        if (p.action === 'add') add_(p.text); else tap_(p.id, p.who);
      } finally { lock.releaseLock(); }
    }
    out = { ok: true, stories: list_() };
  } catch (err) {
    out = { ok: false, error: String(err && err.message || err) };
  }
  return json_(out);
}

function add_(text) {
  text = String(text || '').replace(/^\s+|\s+$/g, '');
  if (!text) throw new Error('The story is empty');
  if (text.length > MAX_TEXT) throw new Error('The story is too long');
  stories_().appendRow([Utilities.getUuid().substring(0, 8),
                        Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm'), text]);
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
  sh.appendRow([ymd_(new Date()), who, dstr_(story[1]).slice(0, 10), String(story[2]), String(id)]);
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
    out.push({ id: String(r[0]), added: added, text: String(r[2]), taps: taps[String(r[0])] || {} });
  });
  out.reverse();  // newest first
  return out;
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
    return { tapped: dstr_(r[0]).slice(0, 10), who: String(r[1]), added: dstr_(r[2]).slice(0, 10), text: String(r[3]), id: String(r[4]) };
  }).filter(function (r) { return r.tapped >= from && r.tapped <= through; });
  rows.sort(function (a, b) { return a.tapped < b.tapped ? -1 : a.tapped > b.tapped ? 1 : 0; });

  var groups = [], byKey = {};  // one entry per day per story, listing who used it that day
  rows.forEach(function (r) {
    var k = r.tapped + '|' + r.id;
    if (!byKey[k]) { byKey[k] = { tapped: r.tapped, added: r.added, text: r.text, who: [] }; groups.push(byKey[k]); }
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
    var head = g.who.join(', ') + ' used a story added ' + label_(g.added).replace(/^\w+ /, '');
    plain.push('', head, g.text);
    html.push('<p style="margin:10px 0 2px"><b>' + esc_(head) + '</b></p>' +
              '<div style="white-space:pre-wrap;margin:0 0 6px">' + esc_(g.text) + '</div>');
  });
  MailApp.sendEmail({ to: to, subject: subject, body: plain.join('\n'),
                      htmlBody: '<div style="font-family:Arial,sans-serif;font-size:14px">' + html.join('') + '</div>',
                      name: 'WireReady' });
}

// Run once from the editor (Run > installWeeklyTrigger) to send the log every Monday around 6 AM Central.
function installWeeklyTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'weeklyLog') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('weeklyLog').timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(6).create();
}

// Run once from the editor to create the two sheets with their headers.
function setup() { stories_(); taps_(); }
