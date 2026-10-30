import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { getJSON } from './api.js'
import { Badge, Details, Json, NotCurrent, when } from './ui.jsx'

function Row({ label, children }) {
  if (children === null || children === undefined || children === '') return null
  return <div className="grid grid-cols-[9rem_1fr] gap-2 py-0.5 text-xs"><div className="text-slate-500">{label}</div><div className="break-words">{children}</div></div>
}

function EvidenceDetail({ runKey, id, openPanel }) {
  const [e, setE] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { setE(null); getJSON(`/api/runs/${encodeURIComponent(runKey)}/evidence/${encodeURIComponent(id)}`).then(setE).catch(x => setError(String(x.message))) }, [runKey, id])
  if (error) return <div className="text-sm text-red-700">{error}</div>
  if (!e) return <div className="text-sm">Loading…</div>
  const a = e.applicability || {}, d = e.dates || {}, s = e.scope || {}, au = e.authority || {}, st = e.recorded_states || {}
  return (
    <div className="space-y-3" data-testid="evidence-detail">
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-500">{e.source_type === 'slack_message' ? 'Slack message (saved evidence)' : `${e.source_type || 'source'} (saved evidence)`}</div>
        <h2 className="text-base font-semibold">{e.title}</h2>
        <div className="mt-1 flex flex-wrap gap-1">
          <Badge className="border-slate-300 bg-white">{(e.use || '').replaceAll('_', ' ').toLowerCase()}</Badge>
          {e.cited && <Badge className="border-slate-300 bg-white">cited on the card</Badge>}
          <NotCurrent label={e.superseded_label} />
        </div>
        {e.superseded_label && <div className="mt-2 rounded border border-rose-300 bg-rose-50 p-2 text-xs text-rose-900" data-testid="superseded-banner">
          Not current: {e.superseded_label}. Shown as history only.</div>}
      </div>
      <div>
        <Row label="Source date">{d.source_date ? `${when(d.source_date)} (${d.basis})` : e.timestamp ? when(e.timestamp) : null}</Row>
        <Row label="Effective">{d.effective_at && when(d.effective_at)}</Row>
        <Row label="Valid until">{d.valid_until ? `${when(d.valid_until)}${d.expired_as_of ? ' (expired at the run cutoff)' : ''}` : null}</Row>
        <Row label="Checked as of">{d.reference_time && when(d.reference_time)}</Row>
        <Row label="Scope">{s.scope ? `${s.scope}: ${s.project_id || 'shared'}${s.batch_id ? ` / ${s.batch_id}` : ''}${s.batch_relation ? ` (${s.batch_relation.replaceAll('_', ' ')})` : ''}` : null}</Row>
        <Row label="Applicability">{a.state ? `${a.state.replaceAll('_', ' ').toLowerCase()} (revision ${(a.revision_state || '').replaceAll('_', ' ').toLowerCase()}, ${a.version_mode} view)` : null}</Row>
        <Row label="Replaced by">{(a.replaced_by || []).map(r => `${r.replaced_by}${r.section ? ` (section ${r.section})` : ''}, effective ${r.replacement_effective}`).join('; ')}</Row>
        <Row label="Authority">{au.role ? `${au.role.replaceAll('_', ' ').toLowerCase()} ${au.actor || ''} · ${(au.approval_status || '').replaceAll('_', ' ').toLowerCase()}` : null}</Row>
        <Row label="Recorded states">{Object.entries(st).filter(([, v]) => v).map(([k, v]) => `${k.replace('_status', '')}: ${v}`).join(' · ')}</Row>
        <Row label="Author">{e.author_role ? `${e.author_role.replaceAll('_', ' ').toLowerCase()} (${e.author_id})` : null}</Row>
        <Row label="Link">{e.permalink ? <a className="underline" href={e.permalink} target="_blank" rel="noreferrer">{e.permalink}</a> : 'No Slack permalink stored'}</Row>
        {e.thread_id && <Row label="Thread"><button type="button" className="text-sky-800 underline" data-testid="evidence-thread-link"
          onClick={() => openPanel({ type: 'thread', channel: e.channel_id, thread: e.thread_id })}>Open the internal thread view</button></Row>}
      </div>
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Saved text</div>
        <div className="prose-pre mt-1 rounded border border-slate-200 bg-white p-2 text-sm" data-testid="evidence-text">{e.excerpt}</div>
      </div>
      <Details summary="Citation IDs">
        <Row label="Evidence ID"><code>{e.evidence_id}</code></Row>
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

function ThreadDetail({ runKey, channel, thread }) {
  const [t, setT] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { setT(null); getJSON(`/api/runs/${encodeURIComponent(runKey)}/threads/${channel}/${thread}`).then(setT).catch(x => setError(String(x.message))) }, [runKey, channel, thread])
  if (error) return <div className="text-sm text-red-700">{error}</div>
  if (!t) return <div className="text-sm">Loading…</div>
  return (
    <div className="space-y-3" data-testid="thread-detail">
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-500">Thread · internal view</div>
        <h2 className="text-base font-semibold">#{t.channel_name} · {t.thread_id}</h2>
        <div className="text-xs text-slate-600">{t.project_id}{t.batch_id ? ` / ${t.batch_id}` : ''}</div>
        <div className={`mt-2 rounded border p-2 text-xs ${t.fixture_status === 'VERIFIED_ORIGINAL' ? 'border-emerald-300 bg-emerald-50' : 'border-amber-300 bg-amber-50'}`}
          data-testid="fixture-status" data-status={t.fixture_status}>
          {t.fixture_status === 'VERIFIED_ORIGINAL' && 'Fixture files match the fingerprint this run recorded: these are the messages the run read.'}
          {t.fixture_status === 'CHANGED_SINCE_RUN' && 'The fixture files changed after this run. Messages below are current fixture content, not the run\'s saved evidence; saved messages are compared individually.'}
          {t.fixture_status === 'NOT_RECORDED' && 'This run did not record a fixture fingerprint. Messages below are current fixture content, separate from the run\'s saved evidence; saved messages are compared individually.'}
        </div>
        <div className="mt-2 rounded border border-slate-200 bg-slate-50 p-2 text-xs" data-testid="permalink-note">
          {t.permalink ? <a className="underline" href={t.permalink} target="_blank" rel="noreferrer">Open in Slack</a>
            : `No Slack permalink is stored for this thread (Slack fixture data, ${t.fixture_root}); this is an internal view of the saved messages.`}
        </div>
      </div>
      <ol className="space-y-2">
        {t.messages.map(m => (
          <li key={m.message_id} className="rounded border border-slate-200 bg-white p-2" data-testid="thread-message">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
              <span className="font-medium text-slate-800">{(m.author_role || 'participant').replaceAll('_', ' ').toLowerCase()}</span>
              <span>{m.author_id}</span><span>{when(m.posted_at)}</span>
              {!m.in_saved_evidence && t.fixture_status !== 'VERIFIED_ORIGINAL' && <Badge className="border-amber-300 bg-amber-50 text-amber-900">current fixture content</Badge>}
              {m.in_saved_evidence && (m.matches_saved_evidence
                ? <Badge className="border-emerald-300 bg-emerald-50 text-emerald-800">matches saved evidence</Badge>
                : <Badge className="border-red-300 bg-red-50 text-red-800">differs from saved evidence</Badge>)}
            </div>
            <div className="prose-pre mt-1 text-sm">{m.text}</div>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function SidePanel({ runKey, panel, openPanel, onClose }) {
  return (
    <AnimatePresence>
      {panel && (
        <motion.aside key={`${panel.type}:${panel.id || panel.thread}`} initial={{ x: 480, opacity: 0 }} animate={{ x: 0, opacity: 1 }}
          exit={{ x: 480, opacity: 0 }} transition={{ type: 'tween', duration: 0.18 }}
          className="fixed inset-y-0 right-0 z-30 w-full max-w-xl overflow-y-auto border-l border-slate-300 bg-slate-50 p-4 shadow-2xl" data-testid="side-panel">
          <div className="mb-3 flex justify-end"><button type="button" className="rounded border border-slate-300 bg-white px-2 py-0.5 text-sm" onClick={onClose}>Close</button></div>
          {panel.type === 'evidence' && <EvidenceDetail runKey={runKey} id={panel.id} openPanel={openPanel} />}
          {panel.type === 'thread' && <ThreadDetail runKey={runKey} channel={panel.channel} thread={panel.thread} />}
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
