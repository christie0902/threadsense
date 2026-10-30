import { motion } from 'framer-motion'
import { useState } from 'react'
import { getJSON } from './api.js'
import DecisionPanel from './DecisionPanel.jsx'
import { Badge, CopyButton, Details, Json, LINE_LABELS, NotCurrent, SeverityBadge, SourceBadge } from './ui.jsx'

const LINE_STYLES = { RECOMMENDED_ACTION: 'border-l-emerald-500', NEEDS_REVIEW: 'border-l-amber-500', OBSERVATION: 'border-l-slate-400' }

function Paragraph({ label, children, testid }) {
  return (
    <div className="mt-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="prose-pre mt-0.5 text-sm text-slate-900" data-testid={testid}>{children}</div>
    </div>
  )
}

export default function CardView({ runKey, item, actor, decisionState, onDecisionChanged, openPanel }) {
  const { card, alternatives, cited_evidence: cited, allowed_decisions: allowed, semantic_source: source } = item
  const action = card.recommended_action
  const [detail, setDetail] = useState(null)
  const [detailError, setDetailError] = useState(null)
  const loadDetail = () => {
    if (detail || detailError) return
    getJSON(`/api/runs/${encodeURIComponent(runKey)}/cards/${card.card_id}`).then(setDetail).catch(e => setDetailError(String(e.message)))
  }
  return (
    <motion.article layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}
      className={`rounded-lg border border-l-4 border-slate-200 bg-white p-4 shadow-sm ${LINE_STYLES[card.card_line]}`}
      data-testid="card" data-card-id={card.card_id} data-card-line={card.card_line}>
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="mr-2 text-base font-semibold text-slate-900" data-testid="card-topic">{card.topic_name}</h3>
        <Badge className="border-slate-300 bg-slate-100">{LINE_LABELS[card.card_line]}</Badge>
        <SeverityBadge severity={card.severity} />
        <Badge className="border-slate-300 bg-white">{card.project_id}</Badge>
        <Badge className="border-slate-300 bg-white">{card.resolution_status.replaceAll('_', ' ').toLowerCase()}</Badge>
        <SourceBadge source={source} />
      </header>

      <Paragraph label="What happened" testid="card-summary">{card.summary}</Paragraph>

      {action && action.action_type !== 'NO_ACTION' && (
        <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">What to do</div>
          <div className="mt-0.5 text-sm font-semibold" data-testid="action-label">{action.label}</div>
          {action.instruction && <div className="prose-pre mt-1 text-sm" data-testid="action-instruction">{action.instruction}</div>}
          {action.rationale && <Paragraph label="Why" testid="action-rationale">{action.rationale}</Paragraph>}
          {action.draft_text && (
            <div className="mt-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Draft to copy</span>
                <CopyButton text={action.draft_text} />
              </div>
              <div className="prose-pre mt-1 rounded border border-slate-200 bg-white p-2 text-sm" data-testid="action-draft">{action.draft_text}</div>
            </div>
          )}
          {action.scope_note && <div className="prose-pre mt-2 text-xs text-slate-600">{action.scope_note}</div>}
        </div>
      )}
      {action?.action_type === 'NO_ACTION' && <div className="mt-3 text-sm font-medium text-slate-700" data-testid="action-label">{action.label}</div>}

      {card.review_notes.length > 0 && (
        <div className="mt-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Still needs review</div>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm" data-testid="review-notes">
            {card.review_notes.map((n, i) => <li key={i} className="prose-pre">{n}</li>)}
          </ul>
        </div>
      )}

      {alternatives.length > 0 && (
        <div className="mt-3 rounded border border-indigo-200 bg-indigo-50 p-3" data-testid="alternatives">
          <div className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Supported alternatives</div>
          {alternatives.map(a => (
            <div key={a.candidate_id} className="mt-2 text-sm">
              <div className="font-medium">{a.label}{a.preferred_by_comparison ? ' (preferred in the comparison)' : ''}</div>
              {a.instruction && <div className="prose-pre">{a.instruction}</div>}
              {a.rationale && <div className="prose-pre mt-1 text-xs text-slate-700"><b>Why:</b> {a.rationale}</div>}
              {a.draft_text && <div className="mt-1 flex items-start gap-2"><div className="prose-pre flex-1 rounded border border-indigo-100 bg-white p-2 text-sm">{a.draft_text}</div><CopyButton text={a.draft_text} /></div>}
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Related threads</div>
          <ul className="mt-1 space-y-1 text-sm">
            {card.related_threads.map(t => (
              <li key={t.thread_id}>
                <button type="button" className="text-left text-sky-800 underline decoration-dotted" data-testid="thread-link"
                  onClick={() => openPanel({ type: 'thread', channel: t.channel_id, thread: t.thread_id })}>{t.label}</button>
                <span className="ml-1 text-xs text-slate-500">{t.permalink ? <a className="underline" href={t.permalink} target="_blank" rel="noreferrer">Slack link</a> : 'no Slack link stored'}</span>
              </li>
            ))}
            {card.related_threads.length === 0 && <li className="text-xs text-slate-500">None.</li>}
          </ul>
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Cited sources</div>
          <ul className="mt-1 space-y-1 text-sm" data-testid="cited-sources">
            {cited.filter(e => e.origin === 'retrieved_source' || e.missing_from_ledger).map(e => (
              <li key={e.evidence_id} className="flex flex-wrap items-center gap-1">
                <button type="button" className="text-left text-sky-800 underline decoration-dotted" data-testid="source-link"
                  onClick={() => openPanel({ type: 'evidence', id: e.evidence_id })}>
                  {e.title || e.evidence_id}{e.sections?.length ? ` - ${e.sections.join(', ')}` : ''}
                </button>
                <NotCurrent label={e.superseded_label} />
              </li>
            ))}
            {cited.filter(e => e.origin === 'member_message').length > 0 &&
              <li className="text-xs text-slate-600">{cited.filter(e => e.origin === 'member_message').length} cited messages from the related threads</li>}
          </ul>
        </div>
      </div>

      <div className="mt-4 border-t border-slate-100 pt-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Team-lead decision</div>
        <DecisionPanel runKey={runKey} card={card} alternatives={alternatives} allowed={allowed} actor={actor}
          state={decisionState} onChanged={onDecisionChanged} />
      </div>

      <div className="mt-3 space-y-2" onToggle={loadDetail} onClick={loadDetail}>
        <Details summary="All saved evidence for this card" testid="all-evidence">
          {!detail && !detailError && 'Loading…'}
          {detailError && <span className="text-red-700">{detailError}</span>}
          {detail && (
            <ul className="space-y-1">
              {detail.evidence.map(e => (
                <li key={e.evidence_id} className="flex flex-wrap items-center gap-1">
                  <button type="button" className="text-left text-sky-800 underline decoration-dotted" onClick={() => openPanel({ type: 'evidence', id: e.evidence_id })}>
                    {e.title || e.evidence_id}{e.sections?.length ? ` - ${e.sections.join(', ')}` : ''}
                  </button>
                  <Badge className="border-slate-300 bg-white">{(e.use || e.origin || '').replaceAll('_', ' ').toLowerCase()}</Badge>
                  {e.cited && <Badge className="border-slate-300 bg-white">cited</Badge>}
                  <NotCurrent label={e.superseded_label} />
                </li>
              ))}
            </ul>
          )}
        </Details>
        <Details summary="Technical details (IDs, checks, diagnostics)" testid="technical-details">
          {detail ? <div className="space-y-2">
            <div>Card ID <code>{card.card_id}</code> · confidence {card.confidence} ({card.confidence_band}) · grounding {card.checks.grounding} · temporal {card.checks.temporal_conflict} · open confirmation {card.checks.open_confirmation}</div>
            <div>Review reasons: {card.needs_review_reasons.map(r => r.code).join(', ') || 'none'}</div>
            <Json value={detail.details} />
          </div> : 'Loading…'}
        </Details>
      </div>
    </motion.article>
  )
}
