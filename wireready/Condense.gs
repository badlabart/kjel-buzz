/**
 * Story Editor backend (Boss 2026-11-03). A second file in the WireReady Apps Script project; it shares Code.gs's helpers
 * (prop_, ymd_, daysAgo_, dstr_, sheet_, appendText_, HEADERS).
 *
 * J or R pastes a story and taps "Condense story": Claude rewrites it as broadcast copy in Boss's KJEL style (the rules
 * and her before/after samples are in STYLE below) and the result is saved in the "Condensed" tab. "Add more detail"
 * rewrites the saved story longer from the same source. The page shows the last 7 days, grouped by the day entered.
 *
 * Sheet "Condensed": id | added | by | source | story | status | reason
 *     status = "ok" or "blocked" (a story the KJEL rules keep off the air; reason says why and story is empty)
 *
 * Script property, set from the WireReady menu in the Sheet (never in code or the repo):
 *   CLAUDE_KEY   the Anthropic API key
 */
var EDITORS = ['J', 'R'];
var EDIT_KEEP_DAYS = 7;
var MODEL = 'claude-opus-5-5';
var WORDS_PER_SEC = 2.7;  // Boss's ideal 129-word sample reads at about 48 seconds

function condensed_() {
  HEADERS.Condensed = ['id', 'added', 'by', 'source', 'story', 'status', 'reason'];  // set here, so file load order never matters
  return sheet_('Condensed');
}

function seconds_(story) {
  var words = String(story || '').replace(/\[audio[^\]]*\]/gi, ' ').split(/\s+/).filter(function (w) { return w; }).length;
  return Math.round(words / WORDS_PER_SEC);
}

// STYLE (Boss's rules and samples) lives in Style.gs, which stays out of the public repo.

var SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    story: { type: 'string' },
    reason: { type: 'string' }
  },
  required: ['status', 'story', 'reason'],
  additionalProperties: false
};

function today_() { return Utilities.formatDate(new Date(), TZ, 'EEEE, MMMM d, yyyy'); }

// One Messages API call. Returns {status, story, reason}.
function claude_(userText) {
  var key = prop_('CLAUDE_KEY');
  if (!key) throw new Error('The Story Editor is not switched on yet: the Claude key is missing (WireReady menu > Set Claude API key).');
  var body = {
    model: MODEL,
    max_tokens: 8000,
    fallbacks: 'default',  // a declined request (crime stories can trip a safety check) is retried on Anthropic's fallback model
    output_config: { effort: 'medium', format: { type: 'json_schema', schema: SCHEMA } },
    system: [{ type: 'text', text: STYLE, cache_control: { type: 'ephemeral' } }],  // the rules + samples are the same every call
    messages: [{ role: 'user', content: userText }]
  };
  var r = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
    method: 'post', contentType: 'application/json', muteHttpExceptions: true, payload: JSON.stringify(body),
    headers: { 'x-api-key': key, 'anthropic-version': '2026-10-21', 'anthropic-beta': 'server-side-fallback-2026-07-01' }
  });
  var code = r.getResponseCode(), d = null;
  try { d = JSON.parse(r.getContentText()); } catch (e) {}
  if (code !== 200 || !d) {
    var why = d && d.error && d.error.message ? d.error.message : 'HTTP ' + code;
    throw new Error(code === 429 || code >= 500 ? 'Claude is busy. Wait a minute and try again.' : 'Claude could not edit this story (' + why + ').');
  }
  if (d.stop_reason === 'refusal') return { status: 'blocked', story: '', reason: 'Claude declined to edit this story.' };
  var text = '';
  (d.content || []).forEach(function (b) { if (b.type === 'text' && !text) text = b.text; });  // thinking blocks come first
  var out = JSON.parse(text);
  out.story = String(out.story || '').replace(/^\s+|\s+$/g, '');
  if (out.status === 'ok' && !out.story) throw new Error('Claude returned an empty story. Try again.');
  return out;
}

function condense_(text, by) {
  if (EDITORS.indexOf(by) < 0) throw new Error('Tap J or R first: who is condensing this story?');
  text = String(text || '').replace(/^\s+|\s+$/g, '');
  if (!text) throw new Error('Paste the story first.');
  if (text.length > MAX_TEXT) throw new Error('The story is too long');
  var out = claude_('Today is ' + today_() + '. Use it to turn dates into days of the week.\n\nRewrite this story:\n\n' + text);
  var id = Utilities.getUuid().substring(0, 8);
  locked_(function () {
    appendText_(condensed_(), [id, Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm'), by, text,
                               out.status === 'ok' ? out.story : '', out.status, out.reason || '']);
  });
  return id;
}

// "Add more detail" (Boss 2026-11-03): longer, from the same source only, most important to our core listening area
// first, nothing graphic and nothing a listener has to stop and work out. Capped at 45 seconds.
function moreDetail_(id) {
  var row = findCondensed_(id);
  if (!row) throw new Error('Story not found');
  if (String(row[5]) !== 'ok') throw new Error('A blocked story cannot get more detail.');
  var story = String(row[4]);
  if (seconds_(story) >= 45) throw new Error('This story is already at the 45 second limit.');
  var out = claude_('Today is ' + dstr_(row[1]).slice(0, 10) + ' (the day this story was entered).\n\n' +
    'Here is the source story:\n\n' + String(row[3]) + '\n\nHere is the current broadcast version:\n\n' + story + '\n\n' +
    'Add more detail from the source to the broadcast version. Add only the details most important to our core listening ' +
    'area. Nothing graphic, and nothing a listener cannot take in the moment it is heard. Keep the same style, the tease ' +
    'and the ending. Stay at or under 45 seconds (about 120 words). If the source has nothing more worth adding, return ' +
    'the current version unchanged with status "ok".');
  if (out.status !== 'ok') throw new Error(out.reason || 'Claude could not add detail.');
  locked_(function () {  // the Claude call takes a while, so the row is found again under the lock
    var sh = condensed_(), all = sh.getDataRange().getValues(), j;
    for (j = 1; j < all.length; j++) {
      if (String(all[j][0]) !== String(id)) continue;
      var rg = sh.getRange(j + 1, 5);
      rg.setNumberFormat('@');
      rg.setValue("'" + out.story);
      return;
    }
  });
}

function findCondensed_(id) {
  var rows = condensed_().getDataRange().getValues(), i;
  for (i = 1; i < rows.length; i++) { if (String(rows[i][0]) === String(id)) return rows[i]; }
  return null;
}

// Sheet writes only: the Claude call runs outside the lock so one slow edit never holds up the other person.
function locked_(fn) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try { fn(); } finally { lock.releaseLock(); }
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
  var newId = '';
  if (p.action === 'condense') newId = condense_(p.text, p.by);
  else if (p.action === 'more') moreDetail_(p.id);
  return { ok: true, id: newId || p.id || '', edited: editorList_() };
}

function setClaudeKey() { return ask_('Claude API key', 'Paste the Anthropic API key for the Story Editor.', 'CLAUDE_KEY'); }
