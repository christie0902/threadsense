import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { Icon, LINE_LABELS } from './ui.jsx'

// Above this many cards the progress segments would be too thin to read; a bar with a counter replaces them.
const MAX_SEGMENTS = 12
const SWIPE_PX = 60

/** A blurred, non-interactive glimpse of the neighbouring card; clicking it moves the slider (the card stays intact). */
function Preview({ row, side, onClick }) {
  if (!row) return <div className="hidden md:block" aria-hidden="true" />
  return (
    <button type="button" onClick={onClick} data-testid="slide-preview" data-side={side}
      aria-label={`${side === 'prev' ? 'Previous' : 'Next'} card: ${row.item.display_title || row.card.topic_name}`}
      className="hidden h-[26rem] w-full select-none overflow-hidden rounded-3xl border border-white/10 bg-ink-850/70 p-6 text-left opacity-50 blur-[3px] transition hover:opacity-70 md:block">
      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-cyan-200">{LINE_LABELS[row.card.card_line]}</div>
      <div className="mt-4 font-display text-xl font-semibold leading-snug text-white">{row.item.display_title || row.card.topic_name}</div>
      <p className="mt-4 line-clamp-6 text-sm leading-6 text-slate-200">{row.card.summary}</p>
    </button>
  )
}

function Arrow({ dir, disabled, onClick, testid = `slide-${dir}` }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} data-testid={testid}
      aria-label={dir === 'prev' ? 'Previous card' : 'Next card'}
      className="grid h-12 w-12 shrink-0 place-items-center rounded-full border-2 border-amber-200/80 text-amber-100 transition hover:bg-amber-200/10 disabled:cursor-not-allowed disabled:border-white/15 disabled:text-slate-500">
      <Icon name="chevron" className={`h-5 w-5 ${dir === 'prev' ? 'rotate-180' : ''}`} />
    </button>
  )
}

function Progress({ index, count }) {
  if (count <= MAX_SEGMENTS) {
    return (
      <div className="flex justify-center gap-2" aria-hidden="true">
        {Array.from({ length: count }, (_, i) => (
          <span key={i} className={`h-1 w-10 rounded-full transition-colors ${i === index ? 'bg-amber-200' : 'bg-white/20'}`} />
        ))}
      </div>
    )
  }
  return (
    <div className="mx-auto h-1 w-full max-w-md overflow-hidden rounded-full bg-white/15" aria-hidden="true">
      <div className="h-full rounded-full bg-amber-200 transition-[width]" style={{ width: `${((index + 1) / count) * 100}%` }} />
    </div>
  )
}

/**
 * One card at a time, its neighbours glimpsed at the sides (desktop) and swiped on touch screens. Same rows, same
 * order and the same full card (decision, evidence and alternatives) as the grid; only the arrangement differs.
 * Arrow keys move between cards unless the focus is in a form field.
 */
export default function CardSlider({ rows, renderCard }) {
  const [index, setIndex] = useState(0)
  const [direction, setDirection] = useState(1)
  const touch = useRef(null)
  const count = rows.length
  // A decision can move the current card out of this list: keep the position, so the next card takes its place.
  useEffect(() => { if (index > count - 1) setIndex(Math.max(0, count - 1)) }, [count, index])
  const go = step => {
    const next = Math.min(count - 1, Math.max(0, index + step))
    if (next !== index) { setDirection(step); setIndex(next) }
  }
  const onKey = e => {
    if (e.target.closest('input, textarea, select, [contenteditable]')) return
    if (e.key === 'ArrowLeft') { e.preventDefault(); go(-1) }
    if (e.key === 'ArrowRight') { e.preventDefault(); go(1) }
  }
  const onTouchStart = e => { const t = e.touches[0]; touch.current = { x: t.clientX, y: t.clientY } }
  const onTouchEnd = e => {
    if (!touch.current) return
    const t = e.changedTouches[0], dx = t.clientX - touch.current.x, dy = t.clientY - touch.current.y
    touch.current = null
    if (Math.abs(dx) > SWIPE_PX && Math.abs(dx) > Math.abs(dy) * 1.5) go(dx < 0 ? 1 : -1)
  }
  if (!count) return null
  const current = rows[Math.min(index, count - 1)]

  return (
    <section className="space-y-6 rounded-3xl border border-white/[0.08] bg-gradient-to-b from-cyan-400/[0.10] to-ink-900/40 px-4 py-6 sm:px-6 lg:py-8"
      data-testid="card-slider" aria-roledescription="carousel" aria-label="Advice cards" tabIndex={0} onKeyDown={onKey}>
      <div className="grid items-center gap-4 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,2.4fr)_auto_minmax(0,1fr)] md:gap-6">
        <Preview row={rows[index - 1]} side="prev" onClick={() => go(-1)} />
        <div className="hidden md:block"><Arrow dir="prev" disabled={index === 0} onClick={() => go(-1)} /></div>
        <div className="min-w-0" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd} aria-live="polite">
          <AnimatePresence mode="wait" initial={false} custom={direction}>
            <motion.div key={current.card.card_id} custom={direction}
              initial={{ opacity: 0, x: direction * 48 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: direction * -48 }}
              transition={{ duration: 0.22, ease: 'easeOut' }} className="[&>article]:rounded-3xl">
              {renderCard(current)}
            </motion.div>
          </AnimatePresence>
        </div>
        <div className="hidden md:block"><Arrow dir="next" disabled={index === count - 1} onClick={() => go(1)} /></div>
        <Preview row={rows[index + 1]} side="next" onClick={() => go(1)} />
      </div>
      <div className="space-y-3">
        <Progress index={index} count={count} />
        <div className="flex items-center justify-center gap-4">
          <div className="md:hidden"><Arrow dir="prev" testid="slide-prev-compact" disabled={index === 0} onClick={() => go(-1)} /></div>
          <span className="text-sm font-medium tabular-nums text-slate-200" data-testid="slide-position">Card {index + 1} of {count}</span>
          <div className="md:hidden"><Arrow dir="next" testid="slide-next-compact" disabled={index === count - 1} onClick={() => go(1)} /></div>
        </div>
      </div>
    </section>
  )
}
