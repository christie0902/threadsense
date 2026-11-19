import { Fragment } from 'react'
import { GLOSSARY, annotation, readable } from './text.js'

// Inline: `code`, **bold**, [label](link) and the team abbreviations (LT, QN, TL, L0) with their meaning on hover. A link
// to another knowledge file ("../decisions/….md") has no page in the app, so only its label is shown.
const INLINE = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)\s]+\)|\b(?:LT|QN|TL|L0)\b)/g

/** Saved text as a reader sees it: system wording and dates normalized (text.readable), then inline marks. */
export function Gloss({ text }) {
  if (typeof text !== 'string') return text ?? null
  const parts = readable(text).split(INLINE)
  return parts.map((p, i) => {
    if (i % 2 === 0) return p ? <Fragment key={i}>{p}</Fragment> : null
    if (p.startsWith('`')) return <code key={i} className="rounded bg-white/[0.06] px-1 font-mono text-[0.85em] text-slate-200">{p.slice(1, -1)}</code>
    if (p.startsWith('**')) return <b key={i} className="font-semibold text-slate-100">{p.slice(2, -2)}</b>
    if (p.startsWith('[')) {
      const m = p.match(/^\[([^\]]+)\]\((.+)\)$/)
      return /^https?:\/\//.test(m[2]) ? <a key={i} className="link" href={m[2]} target="_blank" rel="noreferrer">{m[1]}</a>
        : <span key={i} className="font-medium text-slate-200" title="Another knowledge-base document" data-testid="doc-reference">{m[1]}</span>
    }
    return <abbr key={i} title={GLOSSARY[p]} className="cursor-help underline decoration-dotted decoration-slate-500 underline-offset-2">{p}</abbr>
  })
}

const MARKER = /^\[(?:PRIOR RECORD|RELATED RECORD|ADDED FOR TYPE COVERAGE|ANNOUNCEMENT posted|HISTORICAL - NOT CURRENT)[^\]]*\]/

function Table({ lines }) {
  const rows = lines.map(l => l.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim()))
  const [head, ...body] = rows.filter(r => !r.every(c => /^:?-{2,}:?$/.test(c)))
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="text-slate-300"><tr>{head.map((c, i) => <th key={i} className="border-b border-white/10 py-1 pr-3 font-semibold"><Gloss text={c} /></th>)}</tr></thead>
        <tbody className="text-slate-300">{body.map((r, i) => <tr key={i} className="border-b border-white/[0.05] align-top">{r.map((c, j) => <td key={j} className="py-1 pr-3"><Gloss text={c} /></td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

/**
 * The small Markdown subset saved briefs and knowledge sources use: headings, paragraphs, lists, quotes, pipe tables,
 * inline code/bold/links, plus the retrieval annotations shown as notes. Anything else stays plain text.
 */
export default function Markdown({ text, className = '', testid }) {
  const lines = String(text || '').replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  for (let i = 0; i < lines.length;) {
    const line = lines[i]
    if (!line.trim()) { i++; continue }
    const marker = line.trim().match(MARKER)
    if (marker) {
      blocks.push(<div key={i} className="rounded-md border border-amber-300/20 bg-amber-300/[0.05] px-2.5 py-1.5 text-xs text-amber-100/90" data-testid="source-annotation">{annotation(marker[0])}</div>)
      const rest = line.trim().slice(marker[0].length).trim()
      if (rest) lines[i] = rest; else i++
      continue
    }
    const h = line.match(/^(#{1,4})\s+(.*)/)
    if (h) { blocks.push(<div key={i} className={`font-semibold text-slate-100 ${h[1].length <= 2 ? 'text-sm' : 'text-xs uppercase tracking-wide text-slate-300'}`}><Gloss text={h[2]} /></div>); i++; continue }
    if (line.trim().startsWith('|')) {
      const rows = []
      while (i < lines.length && lines[i].trim().startsWith('|')) rows.push(lines[i++])
      blocks.push(<Table key={i} lines={rows} />); continue
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line), items = []
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ''))
      const List = ordered ? 'ol' : 'ul'
      blocks.push(<List key={i} className={`${ordered ? 'list-decimal' : 'list-disc'} space-y-0.5 pl-5`}>{items.map((t, j) => <li key={j}><Gloss text={t} /></li>)}</List>); continue
    }
    if (line.startsWith('>')) {
      const quote = []
      while (i < lines.length && lines[i].startsWith('>')) quote.push(lines[i++].replace(/^>\s?/, ''))
      blocks.push(<blockquote key={i} className="border-l-2 border-cyan-300/30 pl-3 text-slate-300"><Gloss text={quote.join(' ')} /></blockquote>); continue
    }
    const para = []
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|\||>|\s*([-*]|\d+\.)\s)/.test(lines[i]) && !MARKER.test(lines[i].trim())) para.push(lines[i++].trim())
    blocks.push(<p key={i}><Gloss text={para.join(' ')} /></p>)
  }
  return <div className={`space-y-2 ${className}`} data-testid={testid}>{blocks}</div>
}
