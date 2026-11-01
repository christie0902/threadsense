import { AnimatePresence, motion } from 'framer-motion'
import { useRef, useState } from 'react'
import { getJSON } from './api.js'
import DecisionPanel from './DecisionPanel.jsx'
import { Badge, CopyButton, Icon, Json, LINE_LABELS, LINE_TONES, NotCurrent, SeverityBadge, SourceBadge, words } from './ui.jsx'

const ACCENTS = { RECOMMENDED_ACTION: 'bg-emerald-400', NEEDS_REVIEW: 'bg-amber-400', OBSERVATION: 'bg-violet-400' }
const REASON_TONES = { GROUNDING_FAILURE: 'red', TEMPORAL_CONFLICT: 'rose', HIGH_SEVERITY: 'red', INHERITED_FLAG: 'amber' }

function Section({ label, children, testid }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="prose-pre mt-1.5 text-sm leading-relaxed text-slate-200" data-testid={testid}>{children}</div>
    </div>
  )
}

function ActionTab({ action, alternatives, closeCall }) {
  const shown = action && action.action_type !== 'NO_ACTION'
  return (
    <div className="space-y-6">
      {shown && action.rationale && <Section label="Why" testid="action-rationale">{action.rationale}</Section>}
      {shown && action.draft_text && (
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="eyebrow">Draft to copy</span>
            <CopyButton text={action.draft_text} />
          </div>
          <div className="quote mt-2" data-testid="action-draft">{action.draft_text}</div>
        </div>
      )}
      {shown && action.scope_note && <div className="prose-pre text-xs leading-relaxed text-slate-400">{action.scope_note}</div>}
      {alternatives.length > 0 && (
        <section className="rounded-2xl border border-indigo-400/20 bg-indigo-400/[0.05] p-4 sm:p-6" data-testid="alternatives">
          <div className="eyebrow text-indigo-300" data-testid="alternatives-heading">{closeCall ? 'Closely matched options (none preferred)' : 'Supported alternatives'}</div>
          <div className="mt-4 space-y-4">
            {alternatives.map((a, i) => (
              <div key={a.candidate_id} className="rounded-xl border border-white/[0.07] bg-ink-950/40 p-4 sm:p-5">
                <div className="flex items-start gap-3">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-indigo-400/15 text-[11px] font-semibold text-indigo-200">{i + 1}</span>
                  <div className="min-w-0 flex-1 space-y-3">
                    <div className="font-medium leading-snug text-white">{a.label}{a.preferred_by_comparison ? ' (preferred in the comparison)' : ''}</div>
                    {a.instruction && <div className="prose-pre text-sm leading-relaxed text-slate-300">{a.instruction}</div>}
                    {a.rationale && <div className="prose-pre text-xs leading-relaxed text-slate-400"><b className="text-slate-300">Why:</b> {a.rationale}</div>}
                    {a.draft_text && (
                      <div className="space-y-2 pt-1">
                        <div className="flex items-center justify-between gap-3"><span className="eyebrow">Alternative draft</span><CopyButton text={a.draft_text} /></div>
                        <div className="quote">{a.draft_text}</div>
                      </div>
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

function TechnicalTab({ card, detail }) {
  if (!detail) return <span className="text-sm text-slate-400">Loading…</span>
  return (
    <div className="space-y-2 text-xs text-slate-300">
      <div>Card ID <code className="font-mono text-slate-400">{card.card_id}</code> · confidence {card.confidence} ({card.confidence_band}) · grounding {card.checks.grounding} · temporal {card.checks.temporal_conflict} · open confirmation {card.checks.open_confirmation}</div>
      <div>Review reasons: {card.needs_review_reasons.map(r => r.code).join(', ') || 'none'}</div>
      <Json value={detail.details} />
    </div>
  )
}

export default function CardView({ runKey, item, actor, decisionState, onDecisionChanged, openPanel, wide = false }) {
  const { card, alternatives, cited_evidence: cited, allowed_decisions: allowed, semantic_source: source } = item
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
    ...(card.review_notes.length ? [['review', `Review notes (${card.review_notes.length})`]] : []),
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
  const reasons = card.needs_review_reasons || []

  return (
    <motion.article ref={ref} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}
      className={`panel relative scroll-mt-20 self-start overflow-hidden ${open || wide ? 'lg:col-span-2' : ''}`} data-testid="card" data-card-id={card.card_id} data-card-line={card.card_line}>
      <span className={`absolute inset-y-0 left-0 w-[3px] ${ACCENTS[card.card_line]}`} aria-hidden="true" />
      <div className="p-5 pl-6 sm:p-6 sm:pl-7">
        <header className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge tone={LINE_TONES[card.card_line]}>{LINE_LABELS[card.card_line]}</Badge>
              <Badge>{card.project_id}</Badge>
              <SourceBadge source={source} />
              <Badge>{words(card.resolution_status)}</Badge>
            </div>
            <h3 className="mt-2.5 font-display text-lg font-semibold leading-snug text-white" data-testid="card-topic">{card.topic_name}</h3>
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
        <p className={`prose-pre mt-3 text-sm leading-relaxed text-slate-300 ${open ? '' : 'line-clamp-3'}`} data-testid="card-summary">{card.summary}</p>

        {action && action.action_type !== 'NO_ACTION' && (
          <div className={`mt-4 flex items-start gap-3 rounded-xl border border-cyan-400/15 bg-cyan-400/[0.05] p-3 ${open || wide ? 'lg:mt-2' : ''}`}>
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-cyan-400/15 text-cyan-300"><Icon name="spark" /></span>
            <div className="min-w-0">
              <div className="eyebrow text-cyan-300/80" data-testid="action-heading">{closeCall ? 'One option (closely matched; choose one)' : 'Recommended next step'}</div>
              <div className="mt-0.5 font-medium text-white" data-testid="action-label">{action.label}</div>
              {action.instruction && <div className={`prose-pre mt-0.5 text-sm text-slate-300 ${open ? '' : 'line-clamp-2'}`} data-testid="action-instruction">{action.instruction}</div>}
            </div>
          </div>
        )}
        {action?.action_type === 'NO_ACTION' && (
          <div className={`mt-4 flex items-center gap-2 text-sm text-slate-300 ${open || wide ? 'lg:mt-2' : ''}`}><Icon name="eye" className="h-4 w-4 text-violet-300" /><span data-testid="action-label">{action.label}</span></div>
        )}
        </div>

        {reasons.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5" data-testid="review-reasons">
            <span className="mr-1 text-[11px] text-slate-500">Needs a team lead because:</span>
            {reasons.map((r, i) => <Badge key={i} tone={REASON_TONES[r.code] || 'neutral'}>{words(r.code)}</Badge>)}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-white/[0.06] pt-3 text-xs text-slate-400">
          <span className="inline-flex items-center gap-1.5"><Icon name="thread" className="h-3.5 w-3.5" />{card.related_threads.length} threads</span>
          <span className="inline-flex items-center gap-1.5"><Icon name="doc" className="h-3.5 w-3.5" />{sourceCount} cited sources</span>
          {alternatives.length > 0 && <span className="inline-flex items-center gap-1.5"><Icon name="layers" className="h-3.5 w-3.5" />{alternatives.length} alternatives</span>}
          <button type="button" className="btn btn-sm ml-auto" aria-expanded={open} data-testid="card-expand" onClick={toggle}>
            {open ? 'Hide details' : 'Details & evidence'}<Icon name="chevron" className={`h-3.5 w-3.5 transition ${open ? 'rotate-90' : ''}`} />
          </button>
        </div>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div key="detail" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }} className="overflow-hidden" data-testid="card-detail">
              <div role="tablist" className="mt-3 flex flex-wrap gap-1 rounded-xl border border-white/[0.06] bg-ink-950/50 p-1">
                {tabs.map(([t, label]) => (
                  <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => choose(t)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${tab === t ? 'bg-white/[0.08] text-white' : 'text-slate-400 hover:text-slate-200'}`}>{label}</button>
                ))}
              </div>
              <div className="pt-5" role="tabpanel">
                {tab === 'action' && <ActionTab action={action} alternatives={alternatives} closeCall={closeCall} />}
                {tab === 'review' && (
                  <ul className="space-y-3" data-testid="review-notes">
                    {card.review_notes.map((n, i) => (
                      <li key={i} className="prose-pre flex gap-2.5 text-sm leading-relaxed text-slate-200"><Icon name="flag" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" />{n}</li>
                    ))}
                  </ul>
                )}
                {tab === 'sources' && <SourcesTab card={card} cited={cited} openPanel={openPanel} />}
                {tab === 'evidence' && <div data-testid="all-evidence"><EvidenceTab detail={detail} error={detailError} openPanel={openPanel} /></div>}
                {tab === 'technical' && <div data-testid="technical-details"><TechnicalTab card={card} detail={detail} /></div>}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="mt-5 border-t border-white/[0.06] pt-4" data-testid="decision-block">
          <DecisionPanel runKey={runKey} card={card} alternatives={alternatives} allowed={allowed} actor={actor}
            state={decisionState} onChanged={onDecisionChanged} />
        </div>
      </div>
    </motion.article>
  )
}
