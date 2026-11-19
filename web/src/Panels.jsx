import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { getJSON } from './api.js'
import Markdown, { Gloss } from './Markdown.jsx'
import { roleLabel } from './text.js'
import { Badge, CopyButton, Details, Icon, NotCurrent, when, words } from './ui.jsx'

function Row({ label, children }) {
  if (children === null || children === undefined || children === '') return null
  return <div className="grid grid-cols-[8.5rem_1fr] gap-3 border-b border-white/[0.04] py-1.5 text-xs last:border-0"><div className="text-slate-400">{label}</div><div className="break-words text-slate-200">{children}</div></div>
}

// A thread or source the saved briefing does not contain (for example a link typed or kept from elsewhere), in words.
function friendly(error) {
  if (/is not in channel|not referenced by run|is not in the fixture/.test(error))
    return "This thread is not in this briefing's saved Slack data. It may have been posted before the briefing's window; if a card cites it, the saved text is under that card's sources."
  if (/is not saved in run|Not part of the demo data/.test(error)) return 'This source is not saved in this briefing.'
  return error
}

function Loading({ error }) {
  if (error) return <div className="text-sm text-amber-100" data-testid="panel-not-found">{friendly(error)}</div>
  return <div className="text-sm text-slate-400">Loading…</div>
}

function EvidenceDetail({ runKey, id, openPanel }) {
  const [e, setE] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { setE(null); getJSON(`/api/runs/${encodeURIComponent(runKey)}/evidence/${encodeURIComponent(id)}`).then(setE).catch(x => setError(String(x.message))) }, [runKey, id])
  if (!e) return <Loading error={error} />
  const a = e.applicability || {}, d = e.dates || {}, s = e.scope || {}, au = e.authority || {}, st = e.recorded_states || {}
  // Record IDs the text mentions ("safety-fictional-pii-clarification@1.0") by their saved titles.
  const named = t => Object.entries(e.record_names || {}).reduce((acc, [k, v]) => acc.split(k).join(`“${v}”`), String(t || ''))
  return (
    <div className="space-y-5" data-testid="evidence-detail">
      <div>
        <div className="eyebrow">{e.source_type === 'slack_message' ? 'Slack message (saved copy)' : `${words(e.source_type) || 'source'} (saved copy)`}</div>
        <h2 className="mt-1 font-display text-lg font-semibold text-white"><Gloss text={e.title} /></h2>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Badge>{words(e.use)}</Badge>
          {e.cited && <Badge tone="cyan">cited on the card</Badge>}
          <NotCurrent label={e.superseded_label} />
        </div>
        {e.superseded_label && <div className="mt-3 rounded-lg border border-rose-400/40 bg-rose-500/10 p-2.5 text-xs text-rose-100" data-testid="superseded-banner">
          Not current: <Gloss text={named(e.superseded_label)} />. Shown as history only.</div>}
      </div>
      <div>
        <div className="eyebrow mb-1">Saved text</div>
        <div className="quote whitespace-normal" data-testid="evidence-text">
          {e.source_type === 'slack_message' ? <div className="prose-pre"><Gloss text={e.excerpt} /></div> : <Markdown text={named(e.excerpt)} />}
        </div>
      </div>
      <div className="panel-inset px-3 py-1">
        <Row label="Source date">{d.source_date ? `${when(d.source_date)} (${words(d.basis)})` : e.timestamp ? when(e.timestamp) : null}</Row>
        <Row label="Effective">{d.effective_at && when(d.effective_at)}</Row>
        <Row label="Valid until">{d.valid_until ? `${when(d.valid_until)}${d.expired_as_of ? ' (expired at the run cutoff)' : ''}` : null}</Row>
        <Row label="Checked as of">{d.reference_time && when(d.reference_time)}</Row>
        <Row label="Scope">{s.scope ? `${s.scope}: ${s.project_id || 'shared'}${s.batch_id ? ` / ${s.batch_id}` : ''}${s.batch_relation ? ` (${s.batch_relation.replaceAll('_', ' ')})` : ''}` : null}</Row>
        <Row label="Applicability">{a.state ? `${words(a.state)} (revision ${words(a.revision_state)}, ${a.version_mode} view)` : null}</Row>
        <Row label="Replaced by">{(e.replaced_by_labels || (a.replaced_by || []).map(r => `${r.replaced_by}${r.section ? ` (section ${r.section})` : ''}, effective ${when(r.replacement_effective, { time: false })}`)).join('; ')}</Row>
        <Row label="Authority">{au.role ? `${words(au.role)} ${au.actor || ''} · ${words(au.approval_status)}` : null}</Row>
        <Row label="Recorded states">{Object.entries(st).filter(([, v]) => v).map(([k, v]) => `${words(k.replace('_status', ''))}: ${words(v).replace(/^tl /, 'team lead ')}`).join(' · ')}</Row>
        <Row label="Author">{e.author_role ? `${roleLabel(e.author_role, { start: true })} (${e.author_id})` : null}</Row>
        {e.permalink && <Row label="Link"><a className="link" href={e.permalink} target="_blank" rel="noreferrer">Open in Slack</a></Row>}
        {e.thread_id && e.thread_available !== false && <Row label="Thread"><button type="button" className="link" data-testid="evidence-thread-link"
          onClick={() => openPanel({ type: 'thread', channel: e.channel_id, thread: e.thread_id })}>Open the whole thread</button></Row>}
        {e.thread_id && e.thread_available === false && <Row label="Thread"><span className="text-slate-400" data-testid="evidence-thread-unavailable">
          Posted before this briefing's Slack window, so the thread itself is not in the saved data. The text above is the saved copy.</span></Row>}
      </div>
      <Details summary="Citation ID (to quote in an AI-issue report)">
        <div className="mb-1 text-slate-400">Copy this into "Supporting source references" when you report an AI issue.</div>
        <div className="flex flex-wrap items-center gap-2" data-testid="citation-id">
          <code className="break-all font-mono text-slate-200">{e.evidence_id}</code><CopyButton text={e.evidence_id} what="ID" />
        </div>
      </Details>
    </div>
  )
}

const FIXTURE_NOTES = {
  VERIFIED_ORIGINAL: ['emerald', 'Fixture files match the fingerprint this run recorded: these are the messages the run read.'],
  CHANGED_SINCE_RUN: ['amber', 'The fixture files changed after this run. Messages below are current fixture content, not the run\'s saved evidence; saved messages are compared individually.'],
  NOT_RECORDED: ['amber', 'This run did not record a fixture fingerprint. Messages below are current fixture content, separate from the run\'s saved evidence; saved messages are compared individually.'],
}
const NOTE_STYLES = { emerald: 'border-emerald-400/30 bg-emerald-400/[0.07] text-emerald-100', amber: 'border-amber-400/30 bg-amber-400/[0.07] text-amber-100' }

function ThreadDetail({ runKey, channel, thread }) {
  const [t, setT] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { setT(null); getJSON(`/api/runs/${encodeURIComponent(runKey)}/threads/${channel}/${thread}`).then(setT).catch(x => setError(String(x.message))) }, [runKey, channel, thread])
  if (!t) return <Loading error={error} />
  const [tone, note] = FIXTURE_NOTES[t.fixture_status] || ['amber', '']
  return (
    <div className="space-y-4" data-testid="thread-detail">
      <div>
        <div className="eyebrow">Thread · internal view</div>
        <h2 className="mt-1 font-display text-lg font-semibold text-white"><span className="text-cyan-300">#</span>{t.channel_name}</h2>
        <div className="text-xs text-slate-400">{t.project_id}{t.batch_id ? ` / ${t.batch_id}` : ''}{t.messages[0] ? ` · started ${when(t.messages[0].posted_at)}` : ''}</div>
        <div className={`mt-3 rounded-lg border p-2.5 text-xs ${NOTE_STYLES[tone]}`} data-testid="fixture-status" data-status={t.fixture_status}>{note}</div>
        <div className="mt-2 rounded-lg border border-white/[0.06] bg-white/[0.02] p-2.5 text-xs text-slate-300" data-testid="permalink-note">
          {t.permalink ? <a className="link" href={t.permalink} target="_blank" rel="noreferrer">Open in Slack</a>
            : 'The saved copy of this thread. The demo data is synthetic, so there is no Slack link.'}
        </div>
      </div>
      <ol className="space-y-2">
        {t.messages.map(m => (
          <li key={m.message_id} className="panel-inset p-3" data-testid="thread-message">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <span className="font-medium text-slate-100">{roleLabel(m.author_role, { start: true })}</span>
              <span className="font-mono">{m.author_id}</span><span>{when(m.posted_at)}</span>
              {!m.in_saved_evidence && t.fixture_status !== 'VERIFIED_ORIGINAL' && <Badge tone="amber">current fixture content</Badge>}
              {m.in_saved_evidence && (m.matches_saved_evidence
                ? <Badge tone="emerald">matches saved evidence</Badge>
                : <Badge tone="red">differs from saved evidence</Badge>)}
            </div>
            <div className="prose-pre mt-1.5 text-sm leading-relaxed text-slate-200"><Gloss text={m.text} /></div>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function SidePanel({ runKey, panel, openPanel, onClose }) {
  const closeRef = useRef(null)
  const open = Boolean(panel)
  useEffect(() => {
    if (!open) return undefined
    // Capture phase, so no other handler on the page can swallow Escape first; focus moves into the panel and back.
    const back = document.activeElement
    const onKey = e => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }
    window.addEventListener('keydown', onKey, true)
    closeRef.current?.focus({ preventScroll: true })
    return () => { window.removeEventListener('keydown', onKey, true); if (back?.isConnected) back.focus({ preventScroll: true }) }
  }, [open, onClose])
  return (
    <AnimatePresence>
      {panel && (
        <>
          <motion.div key="scrim" className="fixed inset-0 z-30 bg-ink-950/60 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            exit={{ opacity: 0 }} onClick={onClose} aria-hidden="true" />
          <motion.aside key={`${panel.type}:${panel.id || panel.thread}`} initial={{ x: 480, opacity: 0 }} animate={{ x: 0, opacity: 1 }}
            exit={{ x: 480, opacity: 0 }} transition={{ type: 'tween', duration: 0.2 }} role="dialog" aria-modal="true"
            className="fixed inset-y-0 right-0 z-40 w-full max-w-xl overflow-y-auto border-l border-white/10 bg-ink-900/95 p-5 shadow-2xl backdrop-blur-xl" data-testid="side-panel">
            <div className="mb-4 flex items-center justify-between">
              <span className="eyebrow inline-flex items-center gap-1.5"><Icon name={panel.type === 'thread' ? 'thread' : 'doc'} className="h-3.5 w-3.5" />{panel.type === 'thread' ? 'Slack thread' : 'Source'}</span>
              <button ref={closeRef} type="button" className="btn btn-sm" onClick={onClose} aria-keyshortcuts="Escape"><Icon name="close" className="h-3.5 w-3.5" />Close</button>
            </div>
            {panel.type === 'evidence' && <EvidenceDetail runKey={runKey} id={panel.id} openPanel={openPanel} />}
            {panel.type === 'thread' && <ThreadDetail runKey={runKey} channel={panel.channel} thread={panel.thread} />}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
