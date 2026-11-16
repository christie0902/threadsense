"""What the dashboard may serve of a card's grounding statements.

Card text comes only from statements the final grounding judged SUPPORTED. Every other statement is withheld: any
other verdict (NOT_JUDGED included), and a SUPPORTED statement the advisor recorded as withheld because it depends on a
withheld one (diagnostics WITHHELD_STATEMENT / ALTERNATIVE_NOT_GROUNDED with `withheld_because`). A reviewer sees a
withheld statement's ID, kind, verdict, the judge's recorded reason and why it was withheld, never its text.

The saved run files keep the text for audit and replay. Every API response that carries statement text goes through
this module, and the static demo bundle (scripts/build_web_demo_data.py) is a snapshot of those responses.
"""

WITHHELD_CODES = ('WITHHELD_STATEMENT', 'ALTERNATIVE_NOT_GROUNDED')


def withheld_ids(result):
    """IDs of the statements kept off the card, from a saved topic result (empty when none was saved)."""
    result = result or {}
    ids = {d['statement_id'] for d in result.get('diagnostics') or []
           if d.get('code') in WITHHELD_CODES and d.get('statement_id')}
    return ids | {s['statement_id'] for s in (result.get('grounding') or {}).get('statements') or []
                  if s.get('verdict') != 'SUPPORTED'}


def without_text(entry, withheld, key='statement_id', field='text'):
    """entry unchanged, or with its text replaced by None and text_withheld set when its statement is withheld."""
    if entry.get(key) not in withheld:
        return entry
    return {**entry, field: None, 'text_withheld': True}


def diagnostics(result):
    """The advisor's saved diagnostics as a reviewer may see them (None when the run saved none)."""
    saved = (result or {}).get('diagnostics')
    if saved is None:
        return None
    held = withheld_ids(result)
    return [without_text(d, held) for d in saved]


def statements(result, reveal=False):
    """Grounding statements as feedback targets: ID, kind, verdict and recorded reason; text only when shown on the
    card. reveal=True keeps every text, for the stored feedback report only (it records the output verbatim)."""
    held = set() if reveal else withheld_ids(result)
    return [without_text({'id': s['statement_id'], 'kind': s['kind'], 'text': s.get('text'), 'verdict': s.get('verdict'),
                          'rationale': s.get('rationale'), 'evidence_ids': s.get('evidence_ids') or []}, held, key='id')
            for s in ((result or {}).get('grounding') or {}).get('statements') or []]


def reports(value, result):
    """value (a feedback view, event or response) with the earlier_text removed from every report target that names a
    withheld statement, wherever it is repeated (report, events, head). The stored rows keep the verbatim text: a
    false-rejection correction needs it in a later run's reviewer context, which is model input, not a reviewer view."""
    held = withheld_ids(result)

    def walk(v):
        if isinstance(v, list):
            return [walk(x) for x in v]
        if not isinstance(v, dict):
            return v
        out = {k: walk(x) for k, x in v.items()}
        t = v.get('target')
        if isinstance(t, dict) and t.get('kind') == 'STATEMENT' and 'earlier_text' in t:
            out['target'] = without_text(t, held, key='id', field='earlier_text')
        return out
    return walk(value)
