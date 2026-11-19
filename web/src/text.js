// Plain-language helpers for text the pipeline saved for machines: upstream verification errors, pipeline notes inside
// saved findings, role and enum names, timestamps. Pure functions over strings, so the views stay simple and the unit
// tests (web/unit) cover them. Saved text is never changed on disk; these only decide how it reads on screen, and every
// caller keeps the original one click away.

// Terms of the annotation teams (data/knowledge/domain_lexicon.json), spelled out wherever they appear.
export const GLOSSARY = {
  LT: 'Label Tool, the internal labeling platform',
  QN: 'Quarantine',
  TL: 'Team lead',
  L0: 'First-pass labelers',
}

export const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`
export const words = s => (s || '').replaceAll('_', ' ').toLowerCase()

const ROLES = { TEAM_LEAD: 'team lead', QA_TUTOR: 'QA tutor', TUTOR: 'tutor', ENGINEER: 'engineer', PARTICIPANT: 'participant' }
/** A role as a reader would write it: "QA tutor", "team lead" (capitalized at the start of a label). */
export function roleLabel(role, { start = false } = {}) {
  const text = ROLES[role] || words(role) || 'participant'
  return start ? text.charAt(0).toUpperCase() + text.slice(1) : text
}
export const article = text => (/^[aeiou]/i.test(text) && !/^(one|uni|use)/i.test(text) ? 'an' : 'a')

// Role and status codes that verifiers copy into their sentences ("The TEAM_LEAD reply …"), in words.
const CODES = /\b(TEAM_LEAD|QA_TUTOR|TUTOR|ENGINEER|RESOLVED_IN_THREAD|PARTIALLY_RESOLVED|UNRESOLVED|NOT_APPLICABLE)\b/g
export const codesInWords = text => String(text || '').replace(CODES, c => ROLES[c] || words(c))

const FIELDS = { central_question: 'central question', summary: 'summary', resolution_rationale: 'resolution reasoning',
  resolution_state: 'resolution status', authority_evidence_message_ids: 'cited answer' }
const field = name => FIELDS[name] || words(name)
const RETRY = /^(Still unverified after one targeted revision|The single targeted revision failed): /

/**
 * An upstream review reason (Agent 1 verification) in plain words: a title, what it means, and optionally what the
 * thread actually shows. The original text is returned as `raw` for a "technical record" disclosure.
 */
export function plainReason(reason) {
  const raw = String(reason || '').trim()
  const retried = RETRY.test(raw)
  const body = raw.replace(RETRY, '').replace(/^(Source analysis|Independent evidence audit) unavailable or invalid: (ValueError: )?/, '')
  const done = (title, explanation, detail = null) => ({
    title, explanation: retried ? `${explanation} One automatic correction was tried and did not fix it.` : explanation,
    detail: detail && codesInWords(detail), raw, translated: true,
  })
  let m
  if (/cited authority evidence without an eligible author role/.test(body))
    return done('Check who answered this thread', "The automatic summary treats a reply as the answer, but that reply was not written or endorsed by a team lead.")
  if (/Substantive reply classifications contradict entirely unanswered coverage/.test(body))
    return done('Check whether the thread was answered', 'The automatic check got conflicting results: one part found a reply that answers the question, another found none.')
  if (/Reply coverage mismatch/.test(body))
    return done('Check which replies were read', "The automatic check could not match its list of replies to the thread, so the summary is not verified.")
  if ((m = body.match(/(\w+):\d+: matching evidence IDs and quotations are required/)))
    return done('Check the summary against the thread', `The automatic check could not tie the ${field(m[1])} to quoted messages in the thread.`)
  if ((m = body.match(/(\w+):\d+: quotation is not verbatim source evidence/)))
    return done('Check a quoted message', `A quotation in the ${field(m[1])} does not match the thread's wording exactly.`)
  if ((m = body.match(/^Prose unit (\w+):\d+: (UNSUPPORTED|CONTRADICTED)\.[\s\S]*?Source establishes: (.*)/))) {
    const verb = m[2] === 'CONTRADICTED' ? 'contradicts the thread' : 'says more than the thread supports'
    return done(`Check the ${field(m[1])}`, `The automatic check found that the ${field(m[1])} ${verb}.`, `What the thread shows: ${m[3].trim()}`)
  }
  if ((m = body.match(/^Independent decision coverage establishes (\w+); interpretation reports (\w+)\.\s*(.*)$/s)))
    return done('Check whether the thread is resolved', `The automatic check read the thread as ${words(m[1])}; the summary says ${words(m[2])}.`, m[3].trim() || null)
  if ((m = body.match(/^The audit found no requested decision, but the interpretation supplies a question\.?/)))
    return done('Check the central question', 'The automatic check found no question asked in the thread, but the summary states one.')
  return { title: "Check this thread's automatic summary", explanation: 'The automatic summary of this thread could not be verified.',
    detail: null, raw, translated: false }
}

// Pipeline notes saved inside a card's findings (agents/advisor_checks.py). They are bookkeeping, not findings.
const THREAD_STATUS = /^Thread status, read from each thread's own messages: (.*)\.$/
const EARLIER_LABELS = /^Agent 1's earlier labels \(an input, not evidence\):/
const HELD = /^(\d+) advisor statements? (was|were) not supported by the evidence and not shown\.$/
const DEPENDS = /^(\d+) (\w+) sentences? (was|were) not shown because (it depends|they depend) on text that was not shown\.$/

/** "resolved in thread ×1, unresolved ×3" -> "1 resolved in thread, 3 unresolved". */
function threadCounts(text) {
  return text.split(/,\s*/).map(part => { const m = part.match(/^(.*?) ×(\d+)$/); return m ? `${m[2]} ${m[1]}` : part }).join(', ')
}

/** A pipeline note in plain words, or null when it is only bookkeeping (dropped from the reader's view). */
export function plainNote(sentence) {
  const s = sentence.trim()
  let m
  if (EARLIER_LABELS.test(s)) return null
  if ((m = s.match(THREAD_STATUS))) return `Threads: ${threadCounts(m[1])}.`
  if ((m = s.match(HELD))) return `${m[1] === '1' ? 'One statement' : `${m[1]} statements`} did not pass the evidence check and ${m[1] === '1' ? 'is' : 'are'} hidden.`
  if ((m = s.match(DEPENDS))) return `${m[1] === '1' ? 'One more sentence is' : `${m[1]} more sentences are`} hidden because ${m[1] === '1' ? 'it builds' : 'they build'} on hidden text.`
  return s
}

// Sentence boundaries: a period, question mark or exclamation followed by a space and a capital, digit or quote.
export function sentences(text) {
  return String(text || '').replace(/\s+/g, ' ').trim().split(/(?<=[.!?])\s+(?=["“A-Z0-9])/).filter(Boolean)
}

const norm = s => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

/**
 * The saved findings as a reader sees them: pipeline notes rewritten or dropped, sentences already shown elsewhere on
 * the card (summary, "What happened") and repeats removed. Returns { sentences, notes } in the saved order.
 */
export function cleanFindings(findings, shown = []) {
  const seen = new Set(shown.flatMap(sentences).map(norm))
  const out = [], notes = []
  for (const s of sentences(findings)) {
    const plain = plainNote(s)
    if (plain === null) continue
    if (plain !== s) { if (!notes.includes(plain)) notes.push(plain); continue }
    const key = norm(s)
    if (!key || seen.has(key)) continue
    seen.add(key)
    out.push(s)
  }
  return { sentences: out, notes }
}

/** Notes such as review_notes or other_notes, with pipeline phrasing rewritten and bookkeeping dropped. */
export function plainNotes(list) {
  return [...new Set((list || []).flatMap(n => sentences(n).map(plainNote)).filter(Boolean))]
}

/** Shortened at a word boundary, never mid-word. */
export function short(text, n = 90) {
  const s = String(text || '').replace(/\s+/g, ' ').trim()
  if (s.length <= n) return s
  const cut = s.slice(0, n - 1)
  return `${cut.slice(0, Math.max(cut.lastIndexOf(' '), n * 0.6)).replace(/[\s,;:.]+$/, '')}…`
}

// Fractions beyond milliseconds ("…00.000901+00:00") are not parsed by every browser; keep three digits.
const iso = value => String(value).replace(/(\.\d{3})\d+/, '$1')
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** One date format across the site: "1 Oct 2026, 22:00 UTC" (day only: "1 Oct 2026"). Unparseable input is returned as is. */
export function when(value, { time = true } = {}) {
  if (!value) return ''
  const d = new Date(iso(value))
  if (Number.isNaN(d.getTime())) return String(value)
  const day = `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`
  if (!time) return day
  return `${day}, ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')} UTC`
}

/** Money with two decimals ("$15.32"); amounts under a cent keep three significant digits so they do not read as zero. */
export function usd(value) {
  if (value == null || Number.isNaN(Number(value))) return ''
  const n = Number(value)
  return n !== 0 && Math.abs(n) < 0.01 ? `$${n.toPrecision(2)}` : `$${n.toFixed(2)}`
}

/**
 * Thread labels that read alike and tell threads apart. Saved labels look like '#channel, 2026-10-02, started by a tutor:
 * "Anyone else seeing this?"'; the date takes the site's format, and when several threads share a label the date
 * becomes the thread's start time. Returns thread_id -> label.
 */
export function threadLabels(threads) {
  const counts = {}
  for (const t of threads || []) counts[t.label] = (counts[t.label] || 0) + 1
  const DAY = /\b\d{4}-\d\d-\d\d\b/
  const out = (threads || []).map(t => {
    const label = String(t.label || '')
    const start = t.thread_id && !Number.isNaN(Number(t.thread_id)) ? new Date(Number(t.thread_id) * 1000).toISOString() : null
    if (counts[t.label] > 1 && start) return [t.thread_id, DAY.test(label) ? label.replace(DAY, when(start)) : `${label} (${when(start)})`, start]
    return [t.thread_id, label.replace(DAY, d => when(d, { time: false })), start]
  })
  // Threads started in the same minute still read alike: add the seconds, then a number if even those match.
  const again = labels => labels.reduce((acc, [, l]) => ({ ...acc, [l]: (acc[l] || 0) + 1 }), {})
  let seen = again(out)
  const withSeconds = out.map(([id, l, start]) => (seen[l] > 1 && start ? [id, l.replace(/(\d\d:\d\d) UTC/, `$1:${start.slice(17, 19)} UTC`), start] : [id, l, start]))
  seen = again(withSeconds)
  const used = {}
  return Object.fromEntries(withSeconds.map(([id, l]) => {
    if (seen[l] < 2) return [id, l]
    used[l] = (used[l] || 0) + 1
    return [id, `${l} (${used[l]})`]
  }))
}

// Statement IDs on the AI-issue form: "claim:c1" -> "Fact 1", "summary:s2" -> "Summary sentence 2".
const STATEMENT_KINDS = { claim: 'Fact', summary: 'Summary sentence', detail: 'Detail', action: 'Action', premise: 'Premise',
  severity: 'Severity', alternative: 'Alternative' }
export function statementLabel(id) {
  const [kind, rest = ''] = String(id).split(':')
  const n = rest.match(/(\d+)/)?.[1]
  const name = STATEMENT_KINDS[kind] || words(kind)
  return n ? `${name} ${n}` : rest && !/^\w+$/.test(rest) ? name : `${name}${rest ? ` (${words(rest)})` : ''}`
}

/** Items (as saved) without the ones whose every sentence is already shown, or repeats an earlier item. */
export function uniqueAgainst(items, shown = []) {
  const seen = new Set(shown.flatMap(sentences).map(norm))
  return (items || []).filter(item => {
    const keys = sentences(item).map(norm).filter(Boolean)
    if (keys.length && keys.every(k => seen.has(k))) return false
    keys.forEach(k => seen.add(k))
    return true
  })
}

// Model-facing annotations saved inside source excerpts ("[PRIOR RECORD (…) - history, not a standing rule.]"), as notes.
const ISO = /\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:\d\d)/g
const dates = s => s.replace(ISO, m => when(m))
/** One annotation as a sentence (dates formatted, enums in words). */
export function annotation(marker) {
  const body = marker.replace(/^\[|\]$/g, '').trim()
  let m
  if ((m = body.match(/^PRIOR RECORD \((\w+); decision_status: (\w+); execution_status: (\w+); outcome_status: (\w+)\)/)))
    return `Earlier record (${words(m[1])}): decision ${words(m[2]).replace(/^tl /, 'team lead ')}, execution ${words(m[3])}, outcome ${words(m[4])}. History, not a standing rule.`
  if ((m = body.match(/^RELATED RECORD - not a search match: recorded (\w+) link from (.+?)\.?$/)))
    return `Related record: reached through a ${m[1]} link from ${m[2]}, not by search.`
  if ((m = body.match(/^ADDED FOR TYPE COVERAGE: best-ranked (\w+) for this query \(rank (\d+)\)/)))
    return `Added so every kind of source is represented: the best-ranked ${m[1].toUpperCase() === 'FAQ' ? 'FAQ' : m[1]} for this search (rank ${m[2]}).`
  if ((m = body.match(/^ANNOUNCEMENT posted (\S+) by (\w+) \(([^)]+)\): (.*)$/)))
    return `Announcement posted ${when(m[1])} by a ${words(m[2])} (${m[3]}). It counts as handling for this topic only when it is relevant and gives a directive.`
  if ((m = body.match(/^HISTORICAL - NOT CURRENT GUIDANCE: (.*)$/)))
    return `Not current guidance: ${dates(m[1]).replace(/valid_until/g, 'valid until')}`
  return dates(body).replaceAll('_', ' ')
}

// ISO timestamps and days inside saved text and labels ("… at 2026-10-02T07:06:16.000064+00:00", "#channel, 2026-10-01,")
// in the site's date format.
// Not inside an identifier: "SC-PII-2026-09-10" or "report_2026-09-10" keeps its date as written.
const ISO_IN_TEXT = /(?<![\w-])\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:\d\d)/g
const DAY_IN_TEXT = /(?<![\w-])\d{4}-\d\d-\d\d(?![\w-])/g
export const datesInText = text => String(text ?? '').replace(ISO_IN_TEXT, m => when(m)).replace(DAY_IN_TEXT, d => when(d, { time: false }))

// Fixed wording the checks write into cards ("The advisor chose…", "Its reason is not shown because…"), in the words the
// rest of the site uses. Only these system phrases change; "not shown in the thread" (a statement about a thread) stays.
const WORDING = [
  [/\bSome advisor statements were not supported by the evidence and are not shown\./g, 'Some statements did not pass the evidence check and are hidden.'],
  [/\bEvidence the advisor needed is missing\b/g, 'Evidence needed for advice is missing'],
  [/\bThe advisor's\b/g, "The AI's"], [/\bthe advisor's\b/g, "the AI's"],
  [/\bThe advisor\b/g, 'The AI'], [/\bthe advisor\b/g, 'the AI'],
  [/\badvisor (statements?)\b/g, '$1'],
  [/: not shown, because\b/g, ': hidden because'],
  [/\bNot shown on this card\b/g, 'Hidden on this card'],
  [/\b(is|are|was|were) not shown\b(?! in the thread)/g, '$1 hidden'],
  [/\bhidden and is not established\b/g, 'hidden and not established'],
]
export function plainWording(text) {
  let s = String(text ?? '')
  for (const [rx, to] of WORDING) s = s.replace(rx, to)
  return s
}
/** Everything a reader sees from saved text: system wording, then dates. */
export const readable = text => datesInText(plainWording(text))

// Statement kinds on the AI-issue form, as a reader would name them (numbered within each kind).
const KIND_NAMES = {
  CLAIM_INCIDENT_FACT: 'Fact', CLAIM_GUIDANCE: 'Guidance', CLAIM_INFERENCE: 'Inference', CLAIM_THREAD_INSTRUCTION: 'Thread instruction',
  CLAIM_HISTORY: 'History', CLAIM_SOURCE_FACT: 'Source fact', DETAIL: 'Detail', SUMMARY: 'Summary sentence', RESOLUTION: 'Thread status',
  AFFECTED_REPORTER: 'Affected reporter', SEVERITY_RATIONALE: 'Severity reason', SEVERITY_SIGNAL: 'Severity signal',
  HISTORICAL_RECURRENCE: 'Earlier occurrence', REPORTED_RECURRENCE: 'Recurrence', ACTION: 'Action', ACTION_RATIONALE: 'Why this action',
  INTERVENTION_NEED: 'Need to act', NO_ACTION_RATIONALE: 'Why no action', ALTERNATIVE: 'Alternative', ANNOUNCEMENT_HANDLING: 'Announcement',
  OPEN_QUESTION: 'Open question', SOURCE_AGREEMENT: 'Sources agree',
}
/** statement id -> "Fact 2", "Thread status 1", … in the order given. */
export function statementNames(statements) {
  const n = {}
  return Object.fromEntries((statements || []).map(s => {
    const name = KIND_NAMES[s.kind] || statementLabel(s.id)
    n[name] = (n[name] || 0) + 1
    return [s.id, `${name} ${n[name]}`]
  }))
}
/**
 * A statement's saved text without internal IDs: "Member thread member_68b6… is UNRESOLVED: …" -> "<thread> is unresolved: …",
 * "U012 reports …" -> "The reporter reports …". memberLabels: member_id -> thread label.
 */
export function statementText(text, memberLabels = {}) {
  return readable(codesInWords(String(text || '')
    .replace(/\bMember thread (member_[0-9a-f]+)/g, (_, m) => (memberLabels[m] ? `The thread ${memberLabels[m]}` : 'A thread'))
    .replace(/\bmember_[0-9a-f]+\b/g, 'a thread')
    .replace(/^U\d{3,}\b/, 'The reporter').replace(/\bU\d{3,}\b/g, 'the reporter')))
}
