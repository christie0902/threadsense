import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { getJSON } from './api.js'
import { Badge, Details, Icon, Json, NotCurrent, when, words } from './ui.jsx'

function Row({ label, children }) {
  if (children === null || children === undefined || children === '') return null
  return <div className="grid grid-cols-[8.5rem_1fr] gap-3 border-b border-white/[0.04] py-1.5 text-xs last:border-0"><div className="text-slate-500">{label}</div><div className="break-words text-slate-200">{children}</div></div>
}

function Loading({ error }) {
  if (error) return <div className="text-sm text-red-300">{error}</div>
  return <div className="text-sm text-slate-400">Loading…</div>
}

function EvidenceDetail({ runKey, id, openPanel }) {
  const [e, setE] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { setE(null); getJSON(`/api/runs/${encodeURIComponent(runKey)}/evidence/${encodeURIComponent(id)}`).then(setE).catch(x => setError(String(x.message))) }, [runKey, id])
  if (!e) return <Loading error={error} />
  const a = e.applicability || {}, d = e.dates || {}, s = e.scope || {}, au = e.authority || {}, st = e.recorded_states || {}
  return (
    <div className="space-y-5" data-testid="evidence-detail">
      <div>
        <div className="eyebrow">{e.source_type === 'slack_message' ? 'Slack message (saved evidence)' : `${e.source_type || 'source'} (saved evidence)`}</div>
        <h2 className="mt-1 font-display text-lg font-semibold text-white">{e.title}</h2>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Badge>{words(e.use)}</Badge>
          {e.cited && <Badge tone="cyan">cited on the card</Badge>}
          <NotCurrent label={e.superseded_label} />
        </div>
        {e.superseded_label && <div className="mt-3 rounded-lg border border-rose-400/40 bg-rose-500/10 p-2.5 text-xs text-rose-100" data-testid="superseded-banner">
          Not current: {e.superseded_label}. Shown as history only.</div>}
      </div>
      <div>
        <div className="eyebrow mb-1">Saved text</div>
        <div className="quote" data-testid="evidence-text">{e.excerpt}</div>
      </div>
      <div className="panel-inset px-3 py-1">
        <Row label="Source date">{d.source_date ? `${when(d.source_date)} (${d.basis})` : e.timestamp ? when(e.timestamp) : null}</Row>
        <Row label="Effective">{d.effective_at && when(d.effective_at)}</Row>
        <Row label="Valid until">{d.valid_until ? `${when(d.valid_until)}${d.expired_as_of ? ' (expired at the run cutoff)' : ''}` : null}</Row>
        <Row label="Checked as of">{d.reference_time && when(d.reference_time)}</Row>
        <Row label="Scope">{s.scope ? `${s.scope}: ${s.project_id || 'shared'}${s.batch_id ? ` / ${s.batch_id}` : ''}${s.batch_relation ? ` (${s.batch_relation.replaceAll('_', ' ')})` : ''}` : null}</Row>
        <Row label="Applicability">{a.state ? `${words(a.state)} (revision ${words(a.revision_state)}, ${a.version_mode} view)` : null}</Row>
        <Row label="Replaced by">{(a.replaced_by || []).map(r => `${r.replaced_by}${r.section ? ` (section ${r.section})` : ''}, effective ${r.replacement_effective}`).join('; ')}</Row>
        <Row label="Authority">{au.role ? `${words(au.role)} ${au.actor || ''} · ${words(au.approval_status)}` : null}</Row>
        <Row label="Recorded states">{Object.entries(st).filter(([, v]) => v).map(([k, v]) => `${k.replace('_status', '')}: ${v}`).join(' · ')}</Row>
        <Row label="Author">{e.author_role ? `${words(e.author_role)} (${e.author_id})` : null}</Row>
        <Row label="Link">{e.permalink ? <a className="link" href={e.permalink} target="_blank" rel="noreferrer">{e.permalink}</a> : 'No Slack permalink stored'}</Row>
        {e.thread_id && <Row label="Thread"><button type="button" className="link" data-testid="evidence-thread-link"
          onClick={() => openPanel({ type: 'thread', channel: e.channel_id, thread: e.thread_id })}>Open the internal thread view</button></Row>}
      </div>
      <Details summary="Citation IDs">
        <Row label="Evidence ID"><code className="font-mono">{e.evidence_id}</code></Row>
        <Row label="Authoring">{e.authoring}</Row>
        <Row label="Sections">{(e.sections || []).join(', ')}</Row>
        <Row label="Document">{e.document_id}</Row>
        <Row label="Version">{e.version_id}</Row>
        <Row label="Chunk">{e.chunk_id}</Row>
        <Json value={{ applicability: e.applicability, dates: e.dates }} />
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
        <h2 className="mt-1 font-display text-lg font-semibold text-white"><span className="text-cyan-300">#</span>{t.channel_name} <span className="font-mono text-sm font-normal text-slate-400">{t.thread_id}</span></h2>
        <div className="text-xs text-slate-400">{t.project_id}{t.batch_id ? ` / ${t.batch_id}` : ''}</div>
        <div className={`mt-3 rounded-lg border p-2.5 text-xs ${NOTE_STYLES[tone]}`} data-testid="fixture-status" data-status={t.fixture_status}>{note}</div>
        <div className="mt-2 rounded-lg border border-white/[0.06] bg-white/[0.02] p-2.5 text-xs text-slate-300" data-testid="permalink-note">
          {t.permalink ? <a className="link" href={t.permalink} target="_blank" rel="noreferrer">Open in Slack</a>
            : `No Slack permalink is stored for this thread (Slack fixture data, ${t.fixture_root}); this is an internal view of the saved messages.`}
        </div>
      </div>
      <ol className="space-y-2">
        {t.messages.map(m => (
          <li key={m.message_id} className="panel-inset p-3" data-testid="thread-message">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <span className="font-medium text-slate-100">{words(m.author_role || 'participant')}</span>
              <span className="font-mono">{m.author_id}</span><span>{when(m.posted_at)}</span>
              {!m.in_saved_evidence && t.fixture_status !== 'VERIFIED_ORIGINAL' && <Badge tone="amber">current fixture content</Badge>}
              {m.in_saved_evidence && (m.matches_saved_evidence
                ? <Badge tone="emerald">matches saved evidence</Badge>
                : <Badge tone="red">differs from saved evidence</Badge>)}
            </div>
            <div className="prose-pre mt-1.5 text-sm leading-relaxed text-slate-200">{m.text}</div>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function SidePanel({ runKey, panel, openPanel, onClose }) {
  useEffect(() => {
    if (!panel) return undefined
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [panel, onClose])
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
              <button type="button" className="btn btn-sm" onClick={onClose}><Icon name="close" className="h-3.5 w-3.5" />Close</button>
            </div>
            {panel.type === 'evidence' && <EvidenceDetail runKey={runKey} id={panel.id} openPanel={openPanel} />}
            {panel.type === 'thread' && <ThreadDetail runKey={runKey} channel={panel.channel} thread={panel.thread} />}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
