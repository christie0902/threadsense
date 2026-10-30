import { useState } from 'react'

export const LINE_LABELS = { RECOMMENDED_ACTION: 'Recommended action', NEEDS_REVIEW: 'Needs review', OBSERVATION: 'Observation' }

const SOURCE_STYLES = {
  LIVE_MODEL: ['Live model', 'bg-emerald-100 text-emerald-800 border-emerald-300'],
  SCRIPTED_PILOT: ['Scripted (prepared judgments)', 'bg-amber-100 text-amber-900 border-amber-300'],
  SCRIPTED_PLACEHOLDER: ['Scripted placeholder (nothing judged)', 'bg-orange-100 text-orange-900 border-orange-300'],
  TEST_FIXTURE: ['Test fixture (hand-written)', 'bg-fuchsia-100 text-fuchsia-900 border-fuchsia-300'],
}

export function Badge({ children, className = '', ...rest }) {
  return <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium ${className}`} {...rest}>{children}</span>
}

export function SourceBadge({ source }) {
  const [label, style] = SOURCE_STYLES[source] || [source || 'Unknown source', 'bg-slate-100 text-slate-700 border-slate-300']
  return <Badge className={style} data-testid="semantic-source">{label}</Badge>
}

export function SeverityBadge({ severity }) {
  const style = { HIGH: 'bg-red-100 text-red-800 border-red-300', MEDIUM: 'bg-amber-100 text-amber-900 border-amber-300',
    LOW: 'bg-sky-100 text-sky-800 border-sky-300' }[severity.level] || 'bg-slate-100 text-slate-700 border-slate-300'
  return <Badge className={style}>Severity {severity.level.toLowerCase()}{severity.assessment_status === 'UNASSESSED' ? ' (unassessed)' : ''}</Badge>
}

export function NotCurrent({ label }) {
  if (!label) return null
  return <Badge className="bg-rose-100 text-rose-800 border-rose-300" data-testid="superseded-label">{label}</Badge>
}

export function CopyButton({ text, what = 'draft' }) {
  const [state, setState] = useState(null)
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setState('ok') } catch { setState('failed') }
  }
  return (
    <span className="inline-flex items-center gap-2">
      <button type="button" onClick={copy} className="rounded border border-slate-300 bg-white px-2 py-0.5 text-xs hover:bg-slate-100">Copy {what}</button>
      {state === 'ok' && <span className="text-xs text-slate-600" data-testid="copy-note">Copied to your clipboard. Nothing was posted.</span>}
      {state === 'failed' && <span className="text-xs text-red-700">Copy failed; select the text instead.</span>}
    </span>
  )
}

export function Details({ summary, children, testid }) {
  return (
    <details className="group rounded border border-slate-200 bg-slate-50" data-testid={testid}>
      <summary className="cursor-pointer select-none px-3 py-1.5 text-xs font-medium text-slate-600">{summary}</summary>
      <div className="border-t border-slate-200 p-3 text-xs">{children}</div>
    </details>
  )
}

export function Json({ value }) {
  return <pre className="prose-pre max-h-96 overflow-auto rounded bg-white p-2 font-mono text-[11px] text-slate-700">{JSON.stringify(value, null, 2)}</pre>
}

export function when(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().replace('T', ' ').replace(/:\d\d(\.\d+)?Z$/, ' UTC')
}

export function textOriginLabel(origin) {
  return { MODEL_GROUNDED: 'Model-grounded text (validated card text, unchanged)', TL_EDITED: 'TL-edited text (not model-grounded)',
    TL_WRITTEN: 'TL-written text (not model-grounded)', NONE: 'No text' }[origin] || origin
}
