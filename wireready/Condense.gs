/**
 * Story Editor backend (Boss 2026-11-03). A second file in the WireReady Apps Script project; it shares Code.gs's helpers
 * (prop_, ymd_, daysAgo_, dstr_, sheet_, appendText_, HEADERS).
 *
 * J or R pastes a story and taps "Condense story": the story is saved here as "queued". Claude on Boss's Mac
 * (scripts/editor_worker.py, every minute, on her Claude plan: no API key, no extra bill) picks it up, rewrites it in her
 * KJEL style and sends it back. "Add more detail" queues the saved story again as "more". The page shows the last 7
 * days, grouped by the day entered.
 *
 * Sheet "Condensed": id | added | by | source | story | status | reason
 *     status = queued | more | ok | blocked (a story the KJEL rules keep off the air; reason says why, story is empty)
 * Script property WORKER_SEEN: when the Mac last asked for work, so the page can say when the Mac is not answering.
 */
var EDITORS = ['B', 'J', 'R'];
var EDIT_KEEP_DAYS = 7;
var WORDS_PER_SEC = 2.7;  // Boss's ideal 129-word sample reads at about 48 seconds

function condensed_() {
  HEADERS.Condensed = ['id', 'added', 'by', 'source', 'story', 'status', 'reason'];  // set here, so file load order never matters
  return sheet_('Condensed');
}

function seconds_(story) {
  var words = String(story || '').replace(/\[audio[^\]]*\]/gi, ' ').split(/\s+/).filter(function (w) { return w; }).length;
  return Math.round(words / WORDS_PER_SEC);
}

function condense_(text, by) {
  if (EDITORS.indexOf(by) < 0) throw new Error('Tap B, J or R first: who is condensing this story?');
  text = String(text || '').replace(/^\s+|\s+$/g, '');
  if (!text) throw new Error('Paste the story first.');
  if (text.length > MAX_TEXT) throw new Error('The story is too long');
  var id = Utilities.getUuid().substring(0, 8);
  appendText_(condensed_(), [id, Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm'), by, text, '', 'queued', '']);
  return id;
}

// Finds a row and hands it to fn(sheet, rowNumber, row).
function withRow_(id, fn) {
  var sh = condensed_(), rows = sh.getDataRange().getValues(), i;
  for (i = 1; i < rows.length; i++) { if (String(rows[i][0]) === String(id)) return fn(sh, i + 1, rows[i]); }
  throw new Error('Story not found');
}
function setCells_(sh, r, col, vals) {
  var rg = sh.getRange(r, col, 1, vals.length);
  rg.setNumberFormat('@');
  rg.setValues([vals.map(function (v) { return "'" + String(v); })]);
}

// "Add more detail" (Boss 2026-11-03): queued again for the Mac, capped at 45 seconds.
function moreDetail_(id) {
  withRow_(id, function (sh, r, row) {
    if (String(row[5]) !== 'ok') throw new Error('Only a finished story can get more detail.');
    if (seconds_(row[4]) >= 45) throw new Error('This story is already at the 45 second limit.');
    setCells_(sh, r, 6, ['more']);
  });
}

// The Mac asks for work: every queued story and every "more" request, oldest first.
function queue_() {
  PropertiesService.getScriptProperties().setProperty('WORKER_SEEN', String(new Date().getTime()));
  return condensed_().getDataRange().getValues().slice(1).filter(function (r) {
    return r[0] && (String(r[5]) === 'queued' || String(r[5]) === 'more');
  }).map(function (r) {
    return { id: String(r[0]), added: dstr_(r[1]).slice(0, 16), source: String(r[3]), story: String(r[4]), status: String(r[5]) };
  });
}

// The Mac sends a finished story back.
function done_(id, status, story, reason) {
  if (status !== 'ok' && status !== 'blocked') throw new Error('Unknown status');
  story = String(story || '').replace(/^\s+|\s+$/g, '');
  if (status === 'ok' && !story) throw new Error('The story is empty');
  if (story.length > MAX_TEXT) throw new Error('The story is too long');
  withRow_(id, function (sh, r, row) {
    if (String(row[5]) === 'more' && status !== 'ok') { setCells_(sh, r, 6, ['ok']); return; }  // keep the story it had
    setCells_(sh, r, 5, [status === 'ok' ? story : '', status, String(reason || '')]);
  });
}

function editorList_() {
  var cutoff = ymd_(daysAgo_(EDIT_KEEP_DAYS - 1)), out = [];  // today and the 6 days before it
  condensed_().getDataRange().getValues().slice(1).forEach(function (r) {
    var added = dstr_(r[1]);
    if (!r[0] || added.slice(0, 10) < cutoff) return;
    out.push({ id: String(r[0]), added: added.slice(0, 16), by: String(r[2]), source: String(r[3]), story: String(r[4]),
               status: String(r[5]), reason: String(r[6] || ''), secs: seconds_(r[4]) });
  });
  out.reverse();  // newest first
  return out;
}

// Called from doPost in Code.gs for the Story Editor actions.
function editorPost_(p) {
  if (p.action === 'queue') return { ok: true, queue: queue_() };
  var newId = '';
  if (p.action === 'condense' || p.action === 'more' || p.action === 'done') {
    var lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      if (p.action === 'condense') newId = condense_(p.text, p.by);
      else if (p.action === 'more') moreDetail_(p.id);
      else done_(p.id, p.status, p.story, p.reason);
    } finally { lock.releaseLock(); }
  }
  var seen = parseInt(prop_('WORKER_SEEN') || '0', 10);
  return { ok: true, id: newId || p.id || '', edited: editorList_(), workerAgo: seen ? Math.round((new Date().getTime() - seen) / 1000) : -1 };
}
