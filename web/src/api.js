import { useCallback, useRef, useState } from 'react'

export async function getJSON(path) {
  const res = await fetch(path)
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(data?.detail || `${res.status} ${res.statusText}`)
  return data
}

function newKey() {
  return `ui-${crypto.randomUUID()}`
}

/**
 * One idempotent save. A retry of the SAME request reuses its key, so a lost response or a double click can
 * never create a second decision; a changed request gets a new key. Success is reported only when the server
 * answers 2xx with persisted: true (after its transaction committed).
 */
export function useIdempotentSave(path) {
  const [state, setState] = useState({ phase: 'idle' })
  const pending = useRef(null) // { key, body } of the last unconfirmed or confirmed request
  const inFlight = useRef(false)

  const save = useCallback(async (body) => {
    if (inFlight.current) return null // double click while saving: ignored (the server would dedupe it too)
    const serialized = JSON.stringify(body)
    if (!pending.current || pending.current.body !== serialized) pending.current = { key: newKey(), body: serialized }
    const { key } = pending.current
    inFlight.current = true
    setState({ phase: 'saving', key })
    let res, data
    try {
      res = await fetch(path, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key }, body: serialized,
      })
      data = await res.json()
    } catch (error) {
      inFlight.current = false
      setState({ phase: 'uncertain', key, error: String(error?.message || error) })
      return null
    }
    inFlight.current = false
    if (res.ok && data?.persisted === true) {
      setState({ phase: 'saved', key, entry: data.entry, replayed: data.replayed })
      return data.entry
    }
    if (res.status === 409) setState({ phase: 'conflict', key, current: data?.current_head, detail: data?.detail })
    else setState({ phase: 'rejected', key, code: data?.code, detail: data?.detail || `${res.status}` })
    if (res.status === 409 || res.status === 422) pending.current = null
    return null
  }, [path])

  const reset = useCallback(() => { pending.current = null; setState({ phase: 'idle' }) }, [])
  return { state, save, reset }
}
