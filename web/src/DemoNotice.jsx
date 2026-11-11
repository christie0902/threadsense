import { useEffect, useState } from 'react'
import { Icon } from './ui.jsx'

// Shown only in the static demo build (npm run build:demo): where the data comes from and where changes are kept.
export default function DemoNotice() {
  const [changes, setChanges] = useState(null)
  const [confirming, setConfirming] = useState(false)
  useEffect(() => {
    const count = () => import('./demoApi.js').then(m => m.demoChangeCount()).then(setChanges).catch(() => setChanges(null))
    count()
    const timer = setInterval(count, 3000)
    return () => clearInterval(timer)
  }, [])
  const reset = async () => { await (await import('./demoApi.js')).resetDemo(); window.location.reload() }
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border border-violet-400/30 bg-violet-400/[0.07] px-3.5 py-2 text-xs text-slate-200" data-testid="demo-notice">
      <span className="inline-flex items-center gap-1.5 font-semibold text-violet-100"><Icon name="doc" className="h-3.5 w-3.5" />Demo data · Changes saved in this browser.</span>
      <span className="text-slate-400">
        A saved synthetic briefing. Decisions, review actions, lessons and AI-issue reports stay in this browser only: no agent runs,
        nothing is posted or sent, and no snapshot for future runs is built.
      </span>
      {changes > 0 && (confirming
        ? <span className="inline-flex items-center gap-2">Clear {changes} saved change{changes === 1 ? '' : 's'}?
          <button type="button" className="btn btn-sm" onClick={reset} data-testid="demo-reset-confirm">Clear</button>
          <button type="button" className="btn btn-sm" onClick={() => setConfirming(false)}>Keep</button></span>
        : <button type="button" className="link" onClick={() => setConfirming(true)} data-testid="demo-reset">Reset demo ({changes})</button>)}
    </div>
  )
}
