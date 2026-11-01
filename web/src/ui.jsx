import { useState } from 'react'

export const LINE_LABELS = { RECOMMENDED_ACTION: 'Recommended action', NEEDS_REVIEW: 'Needs review', OBSERVATION: 'Observation' }

const TONES = {
  neutral: 'border-white/10 bg-white/[0.04] text-slate-300',
  cyan: 'border-cyan-400/30 bg-cyan-400/10 text-cyan-200',
  emerald: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
  amber: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
  orange: 'border-orange-400/30 bg-orange-400/10 text-orange-200',
  red: 'border-red-400/35 bg-red-500/10 text-red-200',
  rose: 'border-rose-400/35 bg-rose-500/10 text-rose-200',
  violet: 'border-violet-400/30 bg-violet-400/10 text-violet-200',
  fuchsia: 'border-fuchsia-400/35 bg-fuchsia-400/10 text-fuchsia-200',
  sky: 'border-sky-400/30 bg-sky-400/10 text-sky-200',
}
export const LINE_TONES = { RECOMMENDED_ACTION: 'emerald', NEEDS_REVIEW: 'amber', OBSERVATION: 'violet' }

const SOURCE_STYLES = {
  LIVE_MODEL: ['Live model', 'emerald'],
  SCRIPTED_PILOT: ['Scripted (prepared judgments)', 'amber'],
  SCRIPTED_PLACEHOLDER: ['Scripted placeholder (nothing judged)', 'orange'],
  TEST_FIXTURE: ['Test fixture (hand-written)', 'fuchsia'],
}

export function Badge({ children, tone = 'neutral', className = '', ...rest }) {
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${TONES[tone] || TONES.neutral} ${className}`} {...rest}>{children}</span>
}

export function SourceBadge({ source }) {
  const [label, tone] = SOURCE_STYLES[source] || [source || 'Unknown source', 'neutral']
  return <Badge tone={tone} data-testid="semantic-source">{label}</Badge>
}

const SEVERITY = { HIGH: ['red', 'bg-red-400'], MEDIUM: ['amber', 'bg-amber-300'], LOW: ['sky', 'bg-sky-300'] }
export function SeverityBadge({ severity }) {
  const [tone, dot] = SEVERITY[severity.level] || ['neutral', 'bg-slate-400']
  const unassessed = severity.assessment_status === 'UNASSESSED'
  return (
    <Badge tone={tone} className="px-2 py-1 text-xs font-semibold" data-testid="severity" title={severity.rationale || undefined}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {SEVERITY[severity.level] ? `${cap(severity.level)} severity` : `Severity ${severity.level.toLowerCase()}`}{unassessed ? ' (unassessed)' : ''}
    </Badge>
  )
}

export function NotCurrent({ label }) {
  if (!label) return null
  return <Badge tone="rose" data-testid="superseded-label">{label}</Badge>
}

export function CopyButton({ text, what = 'draft' }) {
  const [state, setState] = useState(null)
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setState('ok') } catch { setState('failed') }
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button type="button" onClick={copy} className="btn btn-sm"><Icon name="copy" className="h-3.5 w-3.5" />Copy {what}</button>
      {state === 'ok' && <span className="text-xs text-slate-400" data-testid="copy-note">Copied to your clipboard. Nothing was posted.</span>}
      {state === 'failed' && <span className="text-xs text-red-300">Copy failed; select the text instead.</span>}
    </span>
  )
}

/** A native disclosure, so content stays reachable without script and tests can open it by its summary. */
export function Details({ summary, children, testid, className = '' }) {
  return (
    <details className={`group panel-inset ${className}`} data-testid={testid}>
      <summary className="flex cursor-pointer select-none list-none items-center gap-2 px-3 py-2 text-xs font-medium text-slate-300 hover:text-white [&::-webkit-details-marker]:hidden">
        <Icon name="chevron" className="h-3.5 w-3.5 text-slate-500 transition group-open:rotate-90" />{summary}
      </summary>
      <div className="border-t border-white/[0.06] p-3 text-xs text-slate-300">{children}</div>
    </details>
  )
}

export function Json({ value }) {
  return <pre className="prose-pre max-h-96 overflow-auto rounded-lg bg-ink-950/70 p-2 font-mono text-[11px] text-slate-400">{JSON.stringify(value, null, 2)}</pre>
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

export const cap = s => (s ? s.charAt(0) + s.slice(1).toLowerCase() : s)
export const words = s => (s || '').replaceAll('_', ' ').toLowerCase()

const PATHS = {
  chevron: 'M9 6l6 6-6 6',
  alert: 'M12 9v4m0 4h.01M10.3 3.9L2.4 17.5A2 2 0 004.1 20.5h15.8a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z',
  spark: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15z',
  eye: 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zm10 3a3 3 0 100-6 3 3 0 000 6z',
  shield: 'M12 3l8 3v6c0 4.4-3.4 8.3-8 9-4.6-.7-8-4.6-8-9V6l8-3z',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  lock: 'M7 11V8a5 5 0 0110 0v3M5 11h14v10H5z',
  thread: 'M4 5h16v10H8l-4 4V5z',
  doc: 'M7 3h7l5 5v13H7V3zm7 0v5h5',
  queue: 'M4 6h16M4 12h16M4 18h10',
  copy: 'M9 9h11v11H9zM5 15H4V4h11v1',
  close: 'M6 6l12 12M18 6L6 18',
  clock: 'M12 7v5l3 2m6-2a9 9 0 11-18 0 9 9 0 0118 0z',
  flag: 'M5 21V4m0 0h11l-2 4 2 4H5',
  layers: 'M12 3l9 5-9 5-9-5 9-5zm-9 9l9 5 9-5',
}
export function Icon({ name, className = 'h-4 w-4' }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
      className={className} aria-hidden="true"><path d={PATHS[name]} /></svg>
  )
}

/** The ambient mark: an orbit around a core, standing for the overnight agent that prepared the brief. */
export function Orb({ className = 'h-9 w-9', busy = false }) {
  return (
    <span className={`relative inline-grid place-items-center ${className}`} aria-hidden="true">
      <span className="absolute inset-0 rounded-full bg-cyan-400/20 blur-md animate-breathe" />
      <svg viewBox="0 0 40 40" className={`relative h-full w-full ${busy ? 'animate-spin' : 'animate-drift'}`}>
        <defs>
          <linearGradient id="orb-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#67e8f9" /><stop offset="1" stopColor="#818cf8" /></linearGradient>
        </defs>
        <circle cx="20" cy="20" r="17" fill="none" stroke="url(#orb-g)" strokeOpacity="0.35" strokeWidth="1" strokeDasharray="2 4" />
        <ellipse cx="20" cy="20" rx="17" ry="7" fill="none" stroke="url(#orb-g)" strokeOpacity="0.7" strokeWidth="1.2" transform="rotate(-28 20 20)" />
        <circle cx="34.5" cy="13" r="1.8" fill="#67e8f9" />
      </svg>
      <span className="absolute h-[34%] w-[34%] rounded-full bg-gradient-to-br from-cyan-300 to-indigo-400 shadow-[0_0_16px_rgba(103,232,249,0.8)]" />
    </span>
  )
}
