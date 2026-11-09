import { Badge, Icon } from './ui.jsx'

// Why review is needed, kept apart: required by severity, disputed content, a missing fact, an upstream flag, ...
const CATEGORIES = {
  MANDATORY: ['Mandatory review', 'red'],
  DISPUTED: ['Withheld or disputed', 'rose'],
  MISSING: ['Missing fact or step', 'amber'],
  INHERITED: ['Inherited flag', 'violet'],
  CONFLICT: ['Source conflict', 'orange'],
  DECISION: ['For you to decide', 'cyan'],
  OTHER: ['Other', 'neutral'],
}

/** One link to saved evidence, a related thread or a Model Review Queue item. */
function Ref({ link, openPanel, openQueueItem }) {
  if (link.kind === 'queue') return (
    <button type="button" className="link inline-flex items-center gap-1 text-xs" data-testid="review-queue-link"
      onClick={() => openQueueItem(link.item_id)}><Icon name="queue" className="h-3 w-3" />{link.label}</button>
  )
  if (link.kind === 'thread') return (
    <button type="button" className="link inline-flex items-center gap-1 text-left text-xs" data-testid="review-thread-link"
      onClick={() => openPanel({ type: 'thread', channel: link.channel, thread: link.thread })}><Icon name="thread" className="h-3 w-3 shrink-0" />{link.label}</button>
  )
  if (!link.available) return <span className="text-xs text-slate-400">{link.label} (not in this run's saved evidence)</span>
  return (
    <button type="button" className="link inline-flex items-center gap-1 text-left text-xs" data-testid="review-evidence-link"
      onClick={() => openPanel({ type: 'evidence', id: link.id })}><Icon name="doc" className="h-3 w-3 shrink-0" />{link.label}</button>
  )
}

function Refs({ links, openPanel, openQueueItem, max = 3 }) {
  if (!links?.length) return null
  const head = links.slice(0, max), rest = links.slice(max)
  const render = l => <li key={`${l.kind}:${l.id || l.item_id || l.thread}`}><Ref link={l} openPanel={openPanel} openQueueItem={openQueueItem} /></li>
  return (
    <div className="mt-1.5">
      <ul className="space-y-1">{head.map(render)}</ul>
      {rest.length > 0 && (
        <details className="mt-1 text-xs"><summary className="cursor-pointer text-slate-400 hover:text-slate-300">{rest.length} more</summary>
          <ul className="mt-1 space-y-1">{rest.map(render)}</ul></details>
      )}
    </div>
  )
}

function Unavailable({ text }) {
  if (!text) return null
  return <div className="mt-1.5 text-xs text-amber-200/90" data-testid="review-unavailable">Not available in this run: {text}</div>
}

function Withheld({ entry, openPanel, openQueueItem }) {
  return (
    <li className="rounded-lg border border-rose-400/15 bg-rose-500/[0.04] px-3 py-2" data-testid="withheld-entry">
      <div className="text-xs text-slate-200"><b className="font-semibold text-white">{entry.field}</b>: not shown, because {entry.why}.</div>
      {entry.checker_reason && (
        <details className="mt-1 text-xs" data-testid="checker-reason"><summary className="cursor-pointer text-slate-400 hover:text-slate-300">Evidence check's reason (an assessment, not an established fact)</summary>
          <div className="mt-1 leading-relaxed text-slate-400">{entry.checker_reason}</div></details>
      )}
      <Refs links={entry.links} openPanel={openPanel} openQueueItem={openQueueItem} max={2} />
    </li>
  )
}

function countLinks(item) {
  const sub = [...(item.signals || []), ...(item.flags || []), ...(item.withheld || []), ...(item.findings || [])]
  return (item.links || []).length + sub.reduce((n, x) => n + (x.links || []).length, 0)
}

function Item({ item, openPanel, openQueueItem }) {
  const [label, tone] = CATEGORIES[item.category] || CATEGORIES.OTHER
  const parts = (item.signals?.length || 0) + (item.flags?.length || 0) + (item.withheld?.length || 0) + (item.findings?.length || 0)
  const links = countLinks(item)
  const what = item.signals?.length ? `${item.signals.length} rubric signal${item.signals.length === 1 ? '' : 's'}`
    : item.flags?.length ? `${item.flags.length} flag${item.flags.length === 1 ? '' : 's'}`
      : item.withheld?.length ? `${item.withheld.length} withheld field${item.withheld.length === 1 ? '' : 's'}`
        : item.findings?.length ? `${item.findings.length} finding${item.findings.length === 1 ? '' : 's'}` : 'details'
  return (
    <li className="rounded-xl border border-white/[0.07] bg-ink-950/40 p-3.5" data-testid="review-item-reason" data-code={item.code} data-category={item.category}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={tone}>{label}</Badge>
        <span className="text-sm font-medium text-white">{item.title}</span>
      </div>
      {item.check && <div className="prose-pre mt-1.5 text-sm leading-relaxed text-slate-300">{item.check}</div>}
      {(parts > 0 || links > 0) && (
      <details className="group/specifics mt-2" data-testid="review-specifics">
        <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-xs font-medium text-cyan-200/90 hover:text-cyan-100 [&::-webkit-details-marker]:hidden">
          <Icon name="chevron" className="h-3.5 w-3.5 transition group-open/specifics:rotate-90" />Show {what}{links ? ` and ${links} evidence link${links === 1 ? '' : 's'}` : ''}
        </summary>
      <Refs links={item.links} openPanel={openPanel} openQueueItem={openQueueItem} />
      {item.signals?.length > 0 && (
        <ul className="mt-2 space-y-2">
          {item.signals.map((s, i) => (
            <li key={i} className="border-l-2 border-red-400/30 pl-3">
              <div className="text-xs font-medium text-slate-200">Rubric signal: {s.text}</div>
              {s.support && <div className="mt-0.5 text-xs leading-relaxed text-slate-400">{s.support}</div>}
              <Refs links={s.links} openPanel={openPanel} openQueueItem={openQueueItem} max={2} />
            </li>
          ))}
        </ul>
      )}
      {item.flags?.length > 0 && (
        <ul className="mt-2 space-y-2">
          {item.flags.map((f, i) => (
            <li key={i} className="border-l-2 border-violet-400/30 pl-3">
              <div className="text-xs font-medium text-slate-200">{f.label}</div>
              <div className="mt-0.5 text-xs leading-relaxed text-slate-400">{f.check}</div>
              <Refs links={f.links} openPanel={openPanel} openQueueItem={openQueueItem} />
              {f.queue_note && <div className="mt-1 text-xs text-slate-400">{f.queue_note}</div>}
              {f.finding?.findings?.length > 0 && (
                <details className="mt-1 text-xs" data-testid="upstream-finding"><summary className="cursor-pointer text-slate-400 hover:text-slate-300">
                  {f.finding.recovery === 'NOT_NARROWED' ? 'Upstream check failed without naming what is disputed' : 'What the upstream check disputed'} (verbatim; may name people)</summary>
                  {f.finding.findings.map((x, j) => (
                    <div key={j} className="prose-pre mt-1 text-slate-400"><span className="text-slate-400">{x.fields.join(', ')}: </span>{x.text}</div>
                  ))}
                  {f.finding.earlier?.map((x, j) => (
                    <div key={`e${j}`} className="mt-1 text-slate-400" data-testid="earlier-finding">
                      Earlier attempt ({{OPEN: 'still open', UNCERTAIN: 'unclear whether corrected', CORRECTED: 'corrected', SUPERSEDED: 'superseded'}[x.status]}): <span className="prose-pre text-slate-400">{x.fields.join(', ')}: {x.text}</span> <span>{x.basis}</span>
                    </div>
                  ))}
                  {f.finding.attempt_errors?.length > 0 && (
                    <div className="mt-1 text-slate-400">Also recorded (a failed attempt, not the dispute): {f.finding.attempt_errors.map(e => e.text).join(' | ')}</div>
                  )}
                </details>
              )}
              {f.upstream_detail && !f.finding?.findings?.length && (
                <details className="mt-1 text-xs"><summary className="cursor-pointer text-slate-400 hover:text-slate-300">Upstream record (verbatim; may name people)</summary>
                  <div className="prose-pre mt-1 text-slate-400">{f.upstream_detail}</div>
                  {f.finding?.note && <div className="mt-1 text-slate-400">{f.finding.note}</div>}</details>
              )}
            </li>
          ))}
        </ul>
      )}
      {item.withheld?.length > 0 && <ul className="mt-2 space-y-1.5">{item.withheld.map(w => <Withheld key={w.statement_id} entry={w} openPanel={openPanel} openQueueItem={openQueueItem} />)}</ul>}
      {item.findings?.length > 0 && (
        <ul className="mt-2 space-y-2">
          {item.findings.map((f, i) => (
            <li key={i} className="border-l-2 border-orange-400/30 pl-3">
              <div className="text-xs font-medium text-slate-200">{f.what}{f.scope ? ` (${f.scope})` : ''}</div>
              {f.detail && <div className="mt-0.5 text-xs leading-relaxed text-slate-400">{f.detail}</div>}
              <Refs links={f.links} openPanel={openPanel} openQueueItem={openQueueItem} max={2} />
            </li>
          ))}
        </ul>
      )}
      </details>
      )}
      <Unavailable text={item.unavailable} />
    </li>
  )
}

/** "What to review": the card's final review reasons with what to check and where the saved evidence is. */
export default function ReviewPanel({ review, openPanel, openQueueItem }) {
  if (!review) return null
  const listed = new Set(review.items.flatMap(i => (i.withheld || []).map(w => w.statement_id)))
  const otherWithheld = (review.withheld || []).filter(w => !listed.has(w.statement_id))
  if (!review.items.length && !review.advisor_note && !otherWithheld.length && !review.other_notes.length) return null
  return (
    <section className="space-y-3" data-testid="what-to-review">
      {review.items.length > 0 && <ul className="space-y-2.5">{review.items.map((it, i) => <Item key={i} item={it} openPanel={openPanel} openQueueItem={openQueueItem} />)}</ul>}
      {review.advisor_note && (
        <div className="rounded-xl border border-white/[0.07] bg-ink-950/40 p-3.5" data-testid="advisor-review-note">
          <div className="text-xs text-slate-400">Advisor's note</div>
          <div className="prose-pre mt-1 text-sm leading-relaxed text-slate-200">{review.advisor_note.text}</div>
          {review.advisor_note.links.length > 0 && (
            <details className="mt-1.5 text-xs"><summary className="cursor-pointer text-cyan-200/90 hover:text-cyan-100">Show its {review.advisor_note.links.length} evidence link{review.advisor_note.links.length === 1 ? '' : 's'}</summary>
              <Refs links={review.advisor_note.links} openPanel={openPanel} openQueueItem={openQueueItem} max={4} /></details>
          )}
        </div>
      )}
      {otherWithheld.length > 0 && (
        <div className="mt-3" data-testid="other-withheld">
          <div className="text-xs text-slate-400">Also not shown on this card (not a review reason by itself)</div>
          <ul className="mt-1.5 space-y-1.5">{otherWithheld.map(w => <Withheld key={w.statement_id} entry={w} openPanel={openPanel} openQueueItem={openQueueItem} />)}</ul>
        </div>
      )}
      {review.other_notes.length > 0 && (
        <div className="mt-3 text-xs text-slate-300" data-testid="other-notes">
          <div className="text-xs text-slate-400">Also noted</div>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">{review.other_notes.map((n, i) => <li key={i} className="prose-pre">{n}</li>)}</ul>
        </div>
      )}
      {!review.saved_result && <Unavailable text="the topic result was not saved, so evidence links and withheld statements cannot be listed." />}
    </section>
  )
}

const CHECK_TONES = {
  QUESTION: 'border-cyan-400/25 bg-cyan-400/[0.05]', CHOICE: 'border-cyan-400/25 bg-cyan-400/[0.05]',
  CONFLICT: 'border-orange-400/20 bg-orange-400/[0.04]', WITHHELD: 'border-rose-400/20 bg-rose-500/[0.04]',
  FLAG: 'border-violet-400/20 bg-violet-400/[0.04]', SEVERITY: 'border-red-400/20 bg-red-500/[0.04]',
}

function CheckLink({ link, openPanel, openQueueItem }) {
  const act = link.kind === 'queue' ? () => openQueueItem(link.item_id)
    : link.kind === 'thread' ? () => openPanel({ type: 'thread', channel: link.channel, thread: link.thread })
      : () => openPanel({ type: 'evidence', id: link.id })
  if (link.kind === 'evidence' && !link.available) return <span className="text-xs text-slate-400">{link.label} (not saved in this run)</span>
  return (
    <button type="button" onClick={act} data-testid="check-link" data-kind={link.kind}
      className="group/link flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-white/[0.04]">
      <Icon name={link.kind === 'queue' ? 'queue' : link.kind === 'thread' ? 'thread' : 'doc'} className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan-300" />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-cyan-200 group-hover/link:text-cyan-100">{link.label}</span>
        {link.detail && <span className="block truncate text-xs text-slate-400">{link.detail}</span>}
      </span>
    </button>
  )
}

/** What to check: the first thing an opened card shows. Saved text is verbatim; headings and links are UI copy. */
export function WhatToCheck({ checks, openPanel, openQueueItem }) {
  if (!checks?.length) return null
  return (
    <section className="space-y-2.5" data-testid="what-to-check">
      <h4 className="eyebrow text-amber-200/90">What to check</h4>
      {checks.map((c, i) => (
        <div key={i} className={`rounded-xl border p-3.5 ${CHECK_TONES[c.kind] || 'border-white/[0.07] bg-ink-950/40'}`} data-testid="check" data-kind={c.kind}>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{c.heading}</div>
          <div className={`prose-pre mt-1 text-sm leading-relaxed ${c.kind === 'QUESTION' ? 'font-medium text-white' : 'text-slate-200'}`}
            data-testid="check-text" data-origin={c.text_origin}>{c.text}</div>
          {(c.related || []).map((r, j) => <div key={j} className="mt-1.5 text-xs text-slate-400" data-testid="check-related">{r}</div>)}
          {c.note && (
            <div className="mt-2 border-l-2 border-white/10 pl-3 text-xs leading-relaxed text-slate-300" data-testid="check-note">
              <span className="text-slate-400">Advisor's note: </span>{c.note}
            </div>
          )}
          {c.links?.length > 0 && (
            <div className="-mx-2 mt-2 space-y-0.5">
              {c.links.map((l, j) => <CheckLink key={j} link={l} openPanel={openPanel} openQueueItem={openQueueItem} />)}
              {c.more_links > 0 && <div className="px-2 text-xs text-slate-400">{c.more_links} more under "All review reasons and evidence"</div>}
            </div>
          )}
        </div>
      ))}
    </section>
  )
}
