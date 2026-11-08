import { AnimatePresence, motion } from 'framer-motion'
import { useRef, useState } from 'react'
import { getJSON } from './api.js'
import DecisionPanel from './DecisionPanel.jsx'
import ReviewPanel, { WhatToCheck } from './ReviewPanel.jsx'
import { Badge, CopyButton, Icon, Json, LINE_LABELS, LINE_TONES, NotCurrent, SeverityBadge, SourceBadge, words } from './ui.jsx'

const ACCENTS = { RECOMMENDED_ACTION: 'bg-emerald-400', NEEDS_REVIEW: 'bg-amber-400', OBSERVATION: 'bg-violet-400' }
// How an alternative relates to the card's action, only as far as the saved comparison records it (runs.alternatives).
const RELATIONS = {
  INCUMBENT: "The advisor's own proposal, as entered in the option comparison.",
  SAME_ACTION_TYPE: 'Same kind of action as the recommendation, with its own wording, judged separately. The saved comparison does not record that it is the same recommendation.',
  DIFFERENT_ACTION: 'A different kind of action.',
}
const MODES = { LIVE: 'Live model run', SCRIPTED: 'Scripted run (prepared judgments)', TEST_FIXTURE: 'Test fixture (hand-written)' }
// The closed card's line when it shows no action box (next_step from runs.presentation); wording is fixed UI copy.
const STEP_STYLES = {
  NO_ACTION_NEEDED: ['check', 'text-emerald-300'], NO_INTERVENTION_PROPOSED: ['eye', 'text-violet-300'],
  RECOMMENDATION_WITHHELD: ['alert', 'text-amber-300'], NO_RECOMMENDATION_AVAILABLE: ['alert', 'text-slate-400'],
}

function Section({ label, children, testid }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="prose-pre mt-1.5 text-sm leading-relaxed text-slate-200" data-testid={testid}>{children}</div>
    </div>
  )
}

function ActionTab({ action, alternatives, closeCall }) {
  const fromDraft = action?.source === 'DRAFT'
  const shown = action && action.action_type !== 'NO_ACTION'
  return (
    <div className="space-y-6">
      {shown && action.draft_text && (
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="eyebrow">Draft to copy</span>
            <CopyButton text={action.draft_text} />
          </div>
          {action.scope_note && (
            <div className="prose-pre mt-2 rounded-lg border border-amber-300/15 bg-amber-300/[0.04] px-3 py-2 text-xs leading-relaxed text-amber-100/90" data-testid="action-scope">
              <b className="font-semibold">Applies only as stated: </b>{action.scope_note}
            </div>
          )}
          <div className="quote mt-2" data-testid="action-draft">{action.draft_text}</div>
        </div>
      )}
      {shown && !action.draft_text && action.scope_note && (
        <div className="prose-pre text-xs leading-relaxed text-amber-100/90" data-testid="action-scope"><b className="font-semibold">Applies only as stated: </b>{action.scope_note}</div>
      )}
      {alternatives.length > 0 && (
        <section className="rounded-2xl border border-indigo-400/20 bg-indigo-400/[0.05] p-4 sm:p-6" data-testid="alternatives">
          <div className="eyebrow text-indigo-300" data-testid="alternatives-heading">{closeCall ? 'Closely matched options (none preferred)' : 'Supported alternatives'}</div>
          <div className="mt-4 space-y-4">
            {alternatives.map((a, i) => (
              <div key={a.candidate_id} className="rounded-xl border border-white/[0.07] bg-ink-950/40 p-4 sm:p-5" data-testid="alternative" data-relation={a.relation}>
                <div className="flex items-start gap-3">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-indigo-400/15 text-[11px] font-semibold text-indigo-200">{i + 1}</span>
                  <div className="min-w-0 flex-1 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium leading-snug text-white">{a.label}</span>
                      {a.preferred_by_comparison && <Badge tone="violet">preferred in the comparison</Badge>}
                    </div>
                    {RELATIONS[a.relation] && (
                      <div className="text-xs leading-relaxed text-indigo-200/80" data-testid="alternative-relation">
                        {RELATIONS[a.relation]}{a.preferred_by_comparison && a.relation === 'SAME_ACTION_TYPE' && fromDraft
                          ? " The card shows the advisor's draft wording of this action; this option was preferred in the comparison." : ''}
                      </div>
                    )}
                    {a.instruction && <div className="prose-pre text-sm leading-relaxed text-slate-300">{a.instruction}</div>}
                    {a.rationale && <div className="prose-pre text-xs leading-relaxed text-slate-400"><b className="text-slate-300">Why:</b> {a.rationale}</div>}
                    {a.draft_text && (
                      <details className="group" data-testid="alternative-draft">
                        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-xs font-medium text-slate-300 hover:text-white [&::-webkit-details-marker]:hidden">
                          <Icon name="chevron" className="h-3.5 w-3.5 text-slate-500 transition group-open:rotate-90" />Show this option's draft
                        </summary>
                        <div className="mt-3 space-y-2">
                          <div className="flex justify-end"><CopyButton text={a.draft_text} /></div>
                          <div className="quote">{a.draft_text}</div>
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
      {!shown && alternatives.length === 0 && <div className="text-sm text-slate-400">No action text on this card.</div>}
    </div>
  )
}

// Processing notes for a pending follow-up, shown only in the opened card.
const KIND_NOTES = {
  WAITING_ON_REQUESTED_STEP: 'A team-lead request in the thread has no recorded answer yet.',
  THREAD_STILL_OPEN: 'The thread was judged still open; no team-lead request is pending.',
  OPEN_QUESTION: 'An open question in the thread was judged supported.',
  MONITORING: 'No action is needed now, but the thread was judged still open.',
}

/** The opened card's account: what happened (detail sentences, or an earlier card's saved findings) and why this next step. */
function Account({ presentation, action }) {
  if (!presentation) return null
  const { details, next_step: step, outstanding_step: outstanding, briefing } = presentation
  const operational = action && action.action_type !== 'NO_ACTION'
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <section data-testid="what-happened" data-source={details.source}>
        <h4 className="eyebrow">What happened</h4>
        {details.source === 'CARD' && details.sentences.length > 0 && (
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm leading-relaxed text-slate-200">
            {details.sentences.map((d, i) => <li key={i} className="prose-pre" data-testid="detail-sentence">{d}</li>)}
          </ul>
        )}
        {details.source === 'CARD' && details.sentences.length === 0 && (
          <div className="mt-1.5 text-sm text-slate-400" data-testid="no-details">No further detail is shown beyond the summary.</div>
        )}
        {details.source === 'SAVED_REASONING' && (
          <details className="group mt-1.5" data-testid="saved-reasoning">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm text-slate-300 hover:text-white [&::-webkit-details-marker]:hidden">
              <Icon name="chevron" className="h-3.5 w-3.5 text-slate-500 transition group-open:rotate-90" />Show the supported findings
            </summary>
            <div className="mt-1 text-[11px] text-slate-500" data-testid="saved-reasoning-note">Saved wording from an earlier card version (written before short and detailed text were separated): the findings that passed the evidence check.</div>
            <div className="prose-pre mt-1.5 text-sm leading-relaxed text-slate-300">{details.findings}</div>
          </details>
        )}
        {details.source === 'CARD' && details.findings && (
          <details className="mt-2 text-xs" data-testid="supported-findings">
            <summary className="cursor-pointer text-slate-500 hover:text-slate-300">All supported findings</summary>
            <div className="prose-pre mt-1 leading-relaxed text-slate-400">{details.findings}</div>
          </details>
        )}
      </section>
      <section data-testid="why-next-step" data-status={step.status}>
        <h4 className="eyebrow">{operational ? 'Why this next step' : step.label}</h4>
        {step.rationale && <div className="prose-pre mt-1.5 text-sm leading-relaxed text-slate-200" data-testid="next-step-rationale">{step.rationale}</div>}
        {step.explanation && <div className="prose-pre mt-1.5 text-sm leading-relaxed text-slate-400" data-testid="next-step-explanation">{step.explanation}</div>}
        {step.derived && <div className="mt-1.5 text-[11px] text-slate-500" data-testid="next-step-derived">Read from this run's saved result (an earlier card version).</div>}
        {outstanding && outstanding.text_source === 'SUPPORTED_STATEMENTS' && (
          <div className="mt-3 text-[11px] leading-relaxed text-slate-500" data-testid="outstanding-detail" data-kind={outstanding.kind}>
            {KIND_NOTES[outstanding.kind] ? `${KIND_NOTES[outstanding.kind]} ` : ''}The text in the highlighted box is saved wording the final evidence check judged supported.
          </div>
        )}
        {briefing && briefing.status !== 'IN_BRIEFING' && (
          <div className="mt-3 text-xs leading-relaxed text-slate-400" data-testid="history-basis">
            <span className="eyebrow">Why it is in history</span>
            <div className="mt-1">{briefing.basis || `Relevance label ${briefing.label_id}.`} Nothing was resolved or deleted; the card, its threads and accounting are unchanged.</div>
          </div>
        )}
      </section>
    </div>
  )
}

function SourcesTab({ card, cited, openPanel }) {
  const sources = cited.filter(e => e.origin === 'retrieved_source' || e.missing_from_ledger)
  const messages = cited.filter(e => e.origin === 'member_message').length
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <div>
        <div className="eyebrow">Related threads</div>
        <ul className="mt-2 space-y-1.5">
          {card.related_threads.map(t => (
            <li key={t.thread_id} className="panel-inset flex items-start gap-2.5 px-3 py-2">
              <span className="mt-0.5 font-mono text-base leading-none text-cyan-300">#</span>
              <div className="min-w-0">
                <button type="button" className="link text-sm" data-testid="thread-link"
                  onClick={() => openPanel({ type: 'thread', channel: t.channel_id, thread: t.thread_id })}>{t.label}</button>
                <div className="text-[11px] text-slate-500">{t.permalink ? <a className="link" href={t.permalink} target="_blank" rel="noreferrer">Slack link</a> : 'No Slack link stored · opens the internal view'}</div>
              </div>
            </li>
          ))}
          {card.related_threads.length === 0 && <li className="text-xs text-slate-500">None.</li>}
        </ul>
      </div>
      <div>
        <div className="eyebrow">Cited sources</div>
        <ul className="mt-2 space-y-1.5" data-testid="cited-sources">
          {sources.map(e => (
            <li key={e.evidence_id} className="panel-inset flex flex-wrap items-center gap-1.5 px-3 py-2">
              <Icon name="doc" className="h-3.5 w-3.5 text-slate-500" />
              <button type="button" className="link text-sm" data-testid="source-link" onClick={() => openPanel({ type: 'evidence', id: e.evidence_id })}>
                {e.title || e.evidence_id}{e.sections?.length ? ` - ${e.sections.join(', ')}` : ''}
              </button>
              <NotCurrent label={e.superseded_label} />
            </li>
          ))}
          {messages > 0 && <li className="px-1 text-xs text-slate-400">{messages} cited messages from the related threads</li>}
          {sources.length === 0 && messages === 0 && <li className="text-xs text-slate-500">None.</li>}
        </ul>
      </div>
    </div>
  )
}

function EvidenceTab({ detail, error, openPanel }) {
  if (error) return <span className="text-sm text-red-300">{error}</span>
  if (!detail) return <span className="text-sm text-slate-400">Loading…</span>
  return (
    <ul className="space-y-1">
      {detail.evidence.map(e => (
        <li key={e.evidence_id} className="flex flex-wrap items-center gap-1.5 rounded-lg px-2 py-1.5 hover:bg-white/[0.03]">
          <button type="button" className="link text-sm" onClick={() => openPanel({ type: 'evidence', id: e.evidence_id })}>
            {e.title || e.evidence_id}{e.sections?.length ? ` - ${e.sections.join(', ')}` : ''}
          </button>
          <Badge>{words(e.use || e.origin)}</Badge>
          {e.cited && <Badge tone="cyan">cited</Badge>}
          <NotCurrent label={e.superseded_label} />
        </li>
      ))}
    </ul>
  )
}

function TechnicalTab({ card, detail, run, displayTitle }) {
  if (!detail) return <span className="text-sm text-slate-400">Loading…</span>
  const prov = run?.provenance || {}
  return (
    <div className="space-y-2 text-xs text-slate-300">
      {card.topic_name !== displayTitle && <div data-testid="saved-title">Saved title: {card.topic_name} · group <code className="font-mono text-slate-400">{card.lineage.candidate_group_id}</code> · no Agent 2 topic</div>}
      {run && <div data-testid="card-provenance">{MODES[run.mode] || run.mode} · run <code className="font-mono text-slate-400">{run.run_key}</code> · prompts {prov.prompt_version || 'not recorded'}{prov.model ? ` · ${prov.model}` : ''}</div>}
      <div>Card ID <code className="font-mono text-slate-400">{card.card_id}</code> · confidence {card.confidence} ({card.confidence_band}) · grounding {card.checks.grounding} · temporal {card.checks.temporal_conflict} · open confirmation {card.checks.open_confirmation}</div>
      <div>Review reasons: {card.needs_review_reasons.map(r => r.code).join(', ') || 'none'}</div>
      <Json value={detail.details} />
    </div>
  )
}

// An editorial clarification from saved records (presentation.json): labelled, attributed, never card text.
function EditorialNote({ note, openPanel }) {
  return (
    <div className="mt-2 rounded-lg border border-amber-300/20 bg-amber-300/[0.04] px-3 py-2 text-xs text-slate-300" data-testid="editorial-note">
      <span className="font-medium text-amber-100">{note.label}</span> <span className="text-slate-500">(editorial note, not judged)</span>: {note.text}
      <span className="ml-1">{note.sources.map(src => (
        <button key={src.evidence_id} type="button" className="link mr-2" data-testid="editorial-source" onClick={() => openPanel?.({ type: 'evidence', id: src.evidence_id })}>source</button>))}</span>
    </div>
  )
}

export default function CardView({ runKey, run, item, actor, decisionState, onDecisionChanged, openPanel, openQueueItem, wide = false }) {
  const { card, alternatives, cited_evidence: cited, allowed_decisions: allowed, semantic_source: source, review, presentation } = item
  const step = presentation?.next_step
  const outstanding = presentation?.outstanding_step
  const briefing = presentation?.briefing
  const displayTitle = item.display_title || card.topic_name
  const action = card.recommended_action
  const closeCall = alternatives.some(a => a.closely_matched)
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  // Collapsing a long card can leave the viewport below it; bring its header back into view.
  const toggle = () => {
    if (open && ref.current && ref.current.getBoundingClientRect().top < 0)
      ref.current.scrollIntoView({ block: 'start', behavior: 'smooth' })
    setOpen(!open)
  }
  const tabs = [
    ...((action && action.action_type !== 'NO_ACTION') || alternatives.length ? [['action', 'Action & draft']] : []),
    ['sources', 'Sources & threads'], ['evidence', 'All evidence'], ['technical', 'Technical'],
  ]
  const [tab, setTab] = useState(tabs[0][0])
  const [detail, setDetail] = useState(null)
  const [detailError, setDetailError] = useState(null)
  const choose = t => {
    setTab(t)
    if ((t === 'evidence' || t === 'technical') && !detail && !detailError)
      getJSON(`/api/runs/${encodeURIComponent(runKey)}/cards/${card.card_id}`).then(setDetail).catch(e => setDetailError(String(e.message)))
  }
  const sourceCount = cited.filter(e => e.origin === 'retrieved_source' || e.missing_from_ledger).length
  const operational = action && action.action_type !== 'NO_ACTION'
  const showDraft = () => { if (!open) setOpen(true); choose('action') }

  return (
    <motion.article ref={ref} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}
      className={`panel relative scroll-mt-20 self-start overflow-hidden ${open || wide ? 'lg:col-span-2' : ''}`} data-testid="card" data-card-id={card.card_id} data-card-line={card.card_line} data-topic-name={card.topic_name}>
      <span className={`absolute inset-y-0 left-0 w-[3px] ${ACCENTS[card.card_line]}`} aria-hidden="true" />
      <div className="p-5 pl-6 sm:p-6 sm:pl-7">
        <header className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge tone={LINE_TONES[card.card_line]}>{LINE_LABELS[card.card_line]}</Badge>
              <Badge>{card.project_id}</Badge>
              <SourceBadge source={source} />
              <Badge>{words(card.resolution_status)}</Badge>
              {briefing && briefing.status !== 'IN_BRIEFING' && presentation?.inventory !== 'CONSOLIDATED_PENDING' && <Badge data-testid="history-badge">Not in this brief · {words(briefing.relevance)}</Badge>}
              {presentation?.consolidated && <Badge data-testid="consolidated-badge">Original topic · combined issue pending</Badge>}
              {presentation?.inventory === 'PROCESSING_HISTORY' && <Badge data-testid="processing-badge">Processing history</Badge>}
              {presentation?.combined && <Badge data-testid="combined-badge">Combined issue · replaces {presentation.combined.replaced_cards.length} earlier cards</Badge>}
            </div>
            <h3 className="mt-2.5 font-display text-lg font-semibold leading-snug text-white" data-testid="card-topic">{displayTitle}</h3>
          </div>
          <div className="flex items-center gap-2">
            <SeverityBadge severity={card.severity} />
            {open && (
              <button type="button" className="btn btn-sm" onClick={toggle} title="Collapse back to the summary" data-testid="card-collapse">
                Collapse<Icon name="close" className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </header>

        <div className={open || wide ? 'lg:grid lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:items-start lg:gap-6' : ''}>
        <p className="prose-pre mt-3 text-sm leading-relaxed text-slate-300" data-testid="card-summary">{card.summary}</p>
        {presentation?.editorial_notes?.filter(n => n.placement === 'SUMMARY').map(n => <EditorialNote key={n.label} note={n} openPanel={openPanel} />)}

        {operational && (
          <div className={`mt-4 flex items-start gap-3 rounded-xl border border-cyan-400/15 bg-cyan-400/[0.05] p-3 ${open || wide ? 'lg:mt-2' : ''}`} data-testid="action-box">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-cyan-400/15 text-cyan-300"><Icon name="spark" /></span>
            <div className="min-w-0">
              <div className="eyebrow text-cyan-300/80" data-testid="action-heading">{closeCall ? 'One option (closely matched; choose one)' : 'Recommended next step'}</div>
              <div className="mt-0.5 font-medium text-white" data-testid="action-label">{action.label}</div>
              {action.instruction && <div className="prose-pre mt-0.5 text-sm leading-relaxed text-slate-300" data-testid="action-instruction">{action.instruction}</div>}
              {action.draft_text && (
                <div className="mt-2.5 flex flex-wrap items-center gap-2">
                  <CopyButton text={action.draft_text} />
                  <button type="button" className="link text-xs" data-testid="show-draft" onClick={showDraft}>Show draft</button>
                </div>
              )}
            </div>
          </div>
        )}
        {presentation?.choice && (
          <div className="mt-2 rounded-lg border border-cyan-400/15 bg-cyan-400/[0.04] px-3 py-2 text-xs text-slate-300" data-testid="choice">
            <div className="font-medium text-cyan-100">{presentation.choice.heading} ({presentation.choice.options.length} options)</div>
            <ol className="mt-1 list-decimal pl-4">{presentation.choice.options.map(o => <li key={o.label} data-testid="choice-option">{o.label}</li>)}</ol>
            <div className="mt-1 text-slate-400">{presentation.choice.basis} Both drafts are under Action &amp; draft.</div>
          </div>
        )}
        {presentation?.editorial_notes?.filter(n => n.placement === 'ACTION').map(n => <EditorialNote key={n.label} note={n} openPanel={openPanel} />)}
        {!operational && step && (
          <div className={`mt-4 flex items-center gap-2 text-sm text-slate-300 ${open || wide ? 'lg:mt-2' : ''}`} data-testid="next-step-status" data-status={step.status}>
            <Icon name={(STEP_STYLES[step.status] || STEP_STYLES.NO_RECOMMENDATION_AVAILABLE)[0]} className={`h-4 w-4 ${(STEP_STYLES[step.status] || STEP_STYLES.NO_RECOMMENDATION_AVAILABLE)[1]}`} />
            <span data-testid="action-label">{action?.action_type === 'NO_ACTION' ? action.label : step.label}</span>
          </div>
        )}
        {!operational && outstanding && (
          <div className="mt-2 rounded-lg border border-amber-300/20 bg-amber-300/[0.05] px-3 py-2 text-sm" data-testid="outstanding-step" data-kind={outstanding.kind}>
            <div className="font-medium text-amber-100" data-testid="outstanding-label">{outstanding.label}</div>
            {outstanding.text_source === 'SUPPORTED_STATEMENTS' && (open
              ? outstanding.details.map((d, i) => <div key={i} className="prose-pre mt-0.5 text-xs leading-relaxed text-slate-300" data-testid="outstanding-text">{d}</div>)
              : <div className="prose-pre mt-0.5 line-clamp-2 text-xs leading-relaxed text-slate-300" data-testid="outstanding-text">{outstanding.details[0]}</div>)}
          </div>
        )}
        {presentation?.human_edits?.length > 0 && (
          <div className="mt-2 rounded-lg border border-violet-300/20 bg-violet-300/[0.05] px-3 py-2 text-xs text-slate-300" data-testid="human-edits">
            <div className="font-medium text-violet-100">Human edits, verified by the live model ({presentation.human_edits.length})</div>
            <ul className="mt-1 list-disc pl-4">
              {presentation.human_edits.map(e => <li key={e.field + e.text} data-testid="human-edit"><span className="text-slate-400">{e.field}:</span> {e.text}</li>)}
            </ul>
          </div>
        )}
        {presentation?.posting_suggestions?.length > 0 && (
          <div className="mt-2 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-slate-300" data-testid="posting-suggestions">
            <div className="font-medium text-slate-100">Posting suggestions for you (not judged; not part of the draft)</div>
            <ul className="mt-1 list-disc pl-4">{presentation.posting_suggestions.map(s => (
              <li key={s.text} data-testid="posting-suggestion"><span className="text-slate-400">{s.label}:</span> {s.text}
                {s.source && <> <button type="button" className="link" data-testid="posting-source" onClick={() => openPanel?.({ type: 'evidence', id: s.source.evidence_id })}>Open the status note</button></>}</li>))}</ul>
          </div>
        )}
        {!presentation?.posting_suggestions?.length && presentation?.tl_suggestions?.map(s => (
          <div key={s.text} className="mt-2 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-slate-300" data-testid="tl-suggestion">
            <span className="font-medium text-slate-100">Suggestion for you (not judged):</span> {s.text}
          </div>
        ))}
        {presentation?.combined && (
          <details className="mt-2 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 text-xs text-slate-400" data-testid="combined-lineage">
            <summary className="cursor-pointer text-slate-300">Earlier cards this issue replaces ({presentation.combined.replaced_cards.length})</summary>
            <p className="mt-1">Same issue ({words(presentation.combined.judgment_provenance)}): {presentation.combined.rationale} This card's advice is {words(presentation.combined.advice_provenance)}; the earlier cards are history and are not briefed.</p>
            <ul className="mt-1 list-disc pl-4">
              {presentation.combined.replaced_cards.map(c => <li key={c.card_id} data-testid="replaced-card">{c.topic_name} ({LINE_LABELS[c.card_line] || words(c.card_line)})</li>)}
            </ul>
          </details>
        )}
        {presentation?.shared_actions?.map(a => (
          <div key={a.action_id} className="mt-2 rounded-lg border border-cyan-400/15 bg-cyan-400/[0.04] px-3 py-2 text-xs text-cyan-100" data-testid="shared-action-note">
            Same edit also proposed by {a.other_cards.map(c => c.topic_name).join('; ')}. Shown once under Shared actions; not a shared cause.
          </div>
        ))}
        {presentation?.unsupported_observation && (
          <div className="mt-2 rounded-lg border border-amber-300/20 bg-amber-300/[0.05] px-3 py-2 text-xs text-amber-100" data-testid="unsupported-observation">
            Filed as an observation without a supported no-action reason: treat it as needing review.
          </div>
        )}
        {!operational && !step && action?.action_type === 'NO_ACTION' && (
          <div className={`mt-4 flex items-center gap-2 text-sm text-slate-300 ${open || wide ? 'lg:mt-2' : ''}`}><Icon name="eye" className="h-4 w-4 text-violet-300" /><span data-testid="action-label">{action.label}</span></div>
        )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-white/[0.06] pt-3 text-xs text-slate-400">
          <span className="inline-flex items-center gap-1.5"><Icon name="thread" className="h-3.5 w-3.5" />{card.related_threads.length} threads</span>
          <span className="inline-flex items-center gap-1.5"><Icon name="doc" className="h-3.5 w-3.5" />{sourceCount} cited sources</span>
          {alternatives.length > 0 && <span className="inline-flex items-center gap-1.5"><Icon name="layers" className="h-3.5 w-3.5" />{alternatives.length} alternative{alternatives.length === 1 ? '' : 's'}</span>}
          <button type="button" className="btn btn-sm ml-auto" aria-expanded={open} data-testid="card-expand" onClick={toggle}>
            {open ? 'Hide details' : review?.checks?.length ? 'What to check & details' : 'Details & evidence'}<Icon name="chevron" className={`h-3.5 w-3.5 transition ${open ? 'rotate-90' : ''}`} />
          </button>
        </div>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div key="detail" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }} className="overflow-hidden" data-testid="card-detail">
              <div className="mt-4 space-y-5">
                <Account presentation={presentation} action={action} />
                <WhatToCheck checks={review?.checks} openPanel={openPanel} openQueueItem={openQueueItem} />
                {review && (review.items.length > 0 || review.withheld?.length > 0 || review.other_notes.length > 0) && (
                  <details className="group panel-inset" data-testid="all-reasons">
                    <summary className="flex cursor-pointer select-none list-none items-center gap-2 px-3 py-2 text-xs font-medium text-slate-300 hover:text-white [&::-webkit-details-marker]:hidden">
                      <Icon name="chevron" className="h-3.5 w-3.5 text-slate-500 transition group-open:rotate-90" />All review reasons and evidence
                    </summary>
                    <div className="border-t border-white/[0.06] p-3"><ReviewPanel review={review} openPanel={openPanel} openQueueItem={openQueueItem} /></div>
                  </details>
                )}
              </div>
              <div role="tablist" className="mt-4 flex flex-wrap gap-1 rounded-xl border border-white/[0.06] bg-ink-950/50 p-1">
                {tabs.map(([t, label]) => (
                  <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => choose(t)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${tab === t ? 'bg-white/[0.08] text-white' : 'text-slate-400 hover:text-slate-200'}`}>{label}</button>
                ))}
              </div>
              <div className="pt-5" role="tabpanel">
                {tab === 'action' && <ActionTab action={action} alternatives={alternatives} closeCall={closeCall} />}
                {tab === 'sources' && <SourcesTab card={card} cited={cited} openPanel={openPanel} />}
                {tab === 'evidence' && <div data-testid="all-evidence"><EvidenceTab detail={detail} error={detailError} openPanel={openPanel} /></div>}
                {tab === 'technical' && <div data-testid="technical-details"><TechnicalTab card={card} detail={detail} run={run} displayTitle={displayTitle} /></div>}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="mt-5 border-t border-white/[0.06] pt-4" data-testid="decision-block">
          <DecisionPanel runKey={runKey} card={card} alternatives={alternatives} allowed={allowed} actor={actor}
            state={decisionState} onChanged={onDecisionChanged} presentation={presentation} />
        </div>
      </div>
    </motion.article>
  )
}
