import assert from 'node:assert/strict'
import test from 'node:test'
import { annotation, cleanFindings, datesInText, plainNote, plainNotes, plainReason, plainWording, readable, short, statementLabel, statementNames, statementText, threadLabels, uniqueAgainst, usd, when } from '../src/text.js'

// Real reason strings from the accepted briefing's Model Review Queue (data/experiments/threadsense_full_v1_combined_v2).
const REASONS = {
  authority: "The single targeted revision failed: ValueError: The model cited authority evidence without an eligible author role or a qualifying TEAM_LEAD endorsement. Ineligible message IDs: ['1790942000.000113']",
  coverage: 'Source analysis unavailable or invalid: ValueError: Substantive reply classifications contradict entirely unanswered coverage.',
  audit: 'Still unverified after one targeted revision: Independent evidence audit unavailable or invalid: ValueError: central_question:1: matching evidence IDs and quotations are required.',
  prose: "Still unverified after one targeted revision: Prose unit central_question:1: UNSUPPORTED.\nCandidate: Why was my tie marked as wrong again by QA on task RP-9595?\nSource establishes: Yuki reports their tie was marked wrong again by QA on task RP-9595, but does not explicitly ask why.\nReason: Yuki's message is a statement of fact.",
  decision: 'Still unverified after one targeted revision: Independent decision coverage establishes RESOLVED_IN_THREAD; interpretation reports PARTIALLY_RESOLVED. The TEAM_LEAD reply provides explicit instructions.',
  verbatim: 'Still unverified after one targeted revision: Independent evidence audit unavailable or invalid: ValueError: summary:3: quotation is not verbatim source evidence.',
  replies: "Source analysis unavailable or invalid: ValueError: Reply coverage mismatch. Missing: []. Unknown: ['1790940838.000005'].",
}

test('every upstream reason in the accepted briefing reads in plain words, with no exception text', () => {
  for (const [name, raw] of Object.entries(REASONS)) {
    const r = plainReason(raw)
    assert.equal(r.translated, true, name)
    assert.equal(r.raw, raw)
    for (const text of [r.title, r.explanation, r.detail || '']) {
      assert.doesNotMatch(text, /ValueError|Prose unit|TEAM_LEAD|RESOLVED_IN_THREAD|\[\'|central_question|:\d+:/, `${name}: ${text}`)
    }
  }
  assert.equal(plainReason(REASONS.authority).title, 'Check who answered this thread')
  assert.match(plainReason(REASONS.audit).explanation, /central question/)
  assert.match(plainReason(REASONS.audit).explanation, /One automatic correction was tried/)
  assert.equal(plainReason(REASONS.prose).detail, 'What the thread shows: Yuki reports their tie was marked wrong again by QA on task RP-9595, but does not explicitly ask why.')
  assert.match(plainReason(REASONS.decision).explanation, /resolved in thread; the summary says partially resolved/)
})

test('an unknown reason still gets a plain title and keeps the original', () => {
  const r = plainReason('Something new went wrong: KeyError: x')
  assert.equal(r.translated, false)
  assert.equal(r.title, "Check this thread's automatic summary")
  assert.equal(r.raw, 'Something new went wrong: KeyError: x')
})

test('pipeline notes in saved findings are rewritten or dropped, and repeats removed', () => {
  assert.equal(plainNote("Agent 1's earlier labels (an input, not evidence): resolved in thread ×1, unresolved ×3."), null)
  assert.equal(plainNote("Thread status, read from each thread's own messages: resolved in thread ×1, unresolved ×3."), 'Threads: 1 resolved in thread, 3 unresolved.')
  assert.equal(plainNote('1 advisor statement was not supported by the evidence and not shown.'), 'One statement did not pass the evidence check and is hidden.')
  assert.equal(plainNote('2 advisor statements were not supported by the evidence and not shown.'), '2 statements did not pass the evidence check and are hidden.')
  const findings = 'A tutor reports a frozen player. QA asked for the task ID. A tutor reports a frozen player. '
    + "Thread status, read from each thread's own messages: unresolved ×2. Agent 1's earlier labels (an input, not evidence): unresolved ×2. "
    + '1 advisor statement was not supported by the evidence and not shown.'
  const { sentences, notes } = cleanFindings(findings, ['QA asked for the task ID.'])
  assert.deepEqual(sentences, ['A tutor reports a frozen player.'])
  assert.deepEqual(notes, ['Threads: 2 unresolved.', 'One statement did not pass the evidence check and is hidden.'])
  assert.deepEqual(plainNotes(['1 advisor statement was not supported by the evidence and not shown.']), ['One statement did not pass the evidence check and is hidden.'])
  assert.deepEqual(uniqueAgainst(['Same as summary.', 'New detail.', 'New detail.'], ['Same as summary.']), ['New detail.'])
})

test('text is shortened at a word boundary', () => {
  const original = 'A tutor reports that QA considers a description borderline and that tutor interpretations differ.'
  const s = short(original, 40)
  assert.ok(s.endsWith('…'))
  assert.ok(s.length <= 40)
  assert.ok(original.split(' ').includes(s.slice(0, -1).split(' ').pop()), s) // the last word is whole
  assert.equal(short('Short enough.', 40), 'Short enough.')
})

test('one date format, including timestamps with microseconds', () => {
  assert.equal(when('2026-10-01T22:00:00.000901+00:00'), '1 Oct 2026, 22:00 UTC')
  assert.equal(when('2026-10-02T12:00:00Z'), '2 Oct 2026, 12:00 UTC')
  assert.equal(when('2026-10-02T12:00:00Z', { time: false }), '2 Oct 2026')
  assert.equal(when('not a date'), 'not a date')
  assert.equal(when(null), '')
})

test('money has two decimals; tiny amounts do not read as zero', () => {
  assert.equal(usd(15.3173), '$15.32')
  assert.equal(usd(0.094), '$0.09')
  assert.equal(usd(0.0012), '$0.0012')
  assert.equal(usd(0), '$0.00')
})

test('threads that open with the same words are told apart', () => {
  // Saved labels as in the accepted briefing: channel, day, who started it, opening words.
  const same = '#multilingual-eval-general, 2026-10-02, started by a tutor: "Anyone else seeing this?"'
  const labels = threadLabels([
    { thread_id: '1790903659.000050', label: same },
    { thread_id: '1790920369.000062', label: same },
    { thread_id: '1790880012.001400', label: '#response-preference-general, 2026-10-01, started by a QA tutor: "Tie marked wrong again"' },
    { thread_id: '1790880000.000002', label: 'Playback freezes on AUD-1' },
  ])
  assert.notEqual(labels['1790903659.000050'], labels['1790920369.000062'])
  assert.match(labels['1790903659.000050'], /^#multilingual-eval-general, 2 Oct 2026, \d\d:\d\d UTC, started by a tutor: "Anyone else seeing this\?"$/)
  assert.equal(labels['1790880012.001400'], '#response-preference-general, 1 Oct 2026, started by a QA tutor: "Tie marked wrong again"')
  assert.equal(labels['1790880000.000002'], 'Playback freezes on AUD-1')
})

test('statement IDs read as names, not IDs', () => {
  assert.equal(statementLabel('claim:c1'), 'Fact 1')
  assert.equal(statementLabel('summary:s2'), 'Summary sentence 2')
  assert.equal(statementLabel('detail:d3'), 'Detail 3')
})

test('retrieval annotations inside source excerpts read as notes', () => {
  assert.equal(annotation('[RELATED RECORD - not a search match: recorded backward link from multi-locale-announcement.]'),
    'Related record: reached through a backward link from multi-locale-announcement, not by search.')
  assert.match(annotation('[PRIOR RECORD (advice_review; decision_status: tl_approved; execution_status: not_executed; outcome_status: not_observed) - history, not a standing rule.]'),
    /^Earlier record \(advice review\): decision team lead approved, execution not executed, outcome not observed\./)
  assert.match(annotation('[HISTORICAL - NOT CURRENT GUIDANCE: valid_until 2026-08-28T21:00:00Z has passed. May explain an old rule; do not apply it as current.]'),
    /^Not current guidance: valid until 28 Aug 2026, 21:00 UTC has passed/)
  assert.match(annotation('[ADDED FOR TYPE COVERAGE: best-ranked faq for this query (rank 12), outside the top 5.]'), /best-ranked FAQ for this search \(rank 12\)/)
})

test('system wording in saved card text reads plainly; statements about threads keep their meaning', () => {
  assert.equal(plainWording('The advisor chose not to propose an intervention. Its reason is not shown because the evidence check found no support.'),
    'The AI chose not to propose an intervention. Its reason is hidden because the evidence check found no support.')
  assert.equal(plainWording('Evidence the advisor needed is missing'), 'Evidence needed for advice is missing')
  assert.equal(plainWording('Finding (source fact): not shown, because rejected source fact presents history as current.'),
    'Finding (source fact): hidden because rejected source fact presents history as current.')
  assert.equal(plainWording('Some advisor statements were not supported by the evidence and are not shown.'), 'Some statements did not pass the evidence check and are hidden.')
  assert.equal(plainWording('Their wording is not shown and is not established.'), 'Their wording is hidden and not established.')
  assert.equal(plainWording('The team lead asked for the target audience; those inputs are not shown in the thread.'),
    'The team lead asked for the target audience; those inputs are not shown in the thread.')
  assert.equal(plainWording('proportionate advisory responses'), 'proportionate advisory responses')
})

test('timestamps and days inside saved text take the site format', () => {
  assert.equal(datesInText('Slack announcement in safety-classification-announcements at 2026-10-02T07:06:16.000064+00:00'),
    'Slack announcement in safety-classification-announcements at 2 Oct 2026, 07:06 UTC')
  assert.equal(datesInText('#multilingual-eval-general, 2026-10-01, started by a tutor'), '#multilingual-eval-general, 1 Oct 2026, started by a tutor')
  assert.equal(readable('The advisor posted 2026-10-01'), 'The AI posted 1 Oct 2026')
})

test('threads started in the same minute still get different labels', () => {
  const same = '#rp-general, 2026-10-01, started by a tutor: "Anyone else seeing this?"'
  const labels = Object.values(threadLabels([
    { thread_id: '1790866003.000036', label: same }, { thread_id: '1790866041.000040', label: same }, { thread_id: '1790866041.000041', label: same },
  ]))
  assert.equal(new Set(labels).size, 3)
  assert.match(labels[1], /14:47:21 UTC/) // same minute: seconds, then a number
  assert.match(labels[0], /14:46 UTC/)
})

test('dates inside document IDs are left alone', () => {
  assert.equal(datesInText('Clarification SC-PII-2026-09-10 (posted 2026-09-10)'), 'Clarification SC-PII-2026-09-10 (posted 10 Sep 2026)')
  assert.equal(datesInText('report_2026-09-10.md'), 'report_2026-09-10.md')
})

test('report-form statements are named by kind and read without internal IDs or codes', () => {
  const names = statementNames([{ id: 'claim:c1', kind: 'CLAIM_INCIDENT_FACT' }, { id: 'resolution:member_68b6c06c', kind: 'RESOLUTION' },
    { id: 'reporter:U008', kind: 'AFFECTED_REPORTER' }, { id: 'claim:c2', kind: 'CLAIM_INCIDENT_FACT' }])
  assert.deepEqual(Object.values(names), ['Fact 1', 'Thread status 1', 'Affected reporter 1', 'Fact 2'])
  assert.equal(statementText('Member thread member_68b6c06c is UNRESOLVED: no answer yet.', { member_68b6c06c: '#rp-general, 1 Oct 2026' }),
    'The thread #rp-general, 1 Oct 2026 is unresolved: no answer yet.')
  assert.equal(statementText('Member thread member_ffff is RESOLVED_IN_THREAD: answered.'), 'A thread is resolved in thread: answered.')
  assert.equal(statementText('U012 reports, in their own cited message, being affected.'), 'The reporter reports, in their own cited message, being affected.')
})
