"""Read-only catalog of overnight runs for the dashboard. Nothing here writes a file or calls a model.

A run is one directory written by agents/overnight.py (morning_brief.json + run_manifest.json). Runs are never
merged: every view is scoped to one run directory, and its mode comes from the run itself (LIVE, SCRIPTED, or
TEST_FIXTURE for the labelled dashboard fixtures). Card text is returned exactly as saved; the dashboard adds
labels around it, never rewording. Evidence comes from the run's saved evidence ledger; thread views come from the
Slack fixture and are compared with the saved excerpts.
"""
from functools import cached_property
from hashlib import sha256
import json
from pathlib import Path

from threadsense.agents.advice_contracts import ACTION_LABELS, AdviceCardV3, ModelReviewItem
from threadsense.retrieval.config import FIXTURE_ROOT
from threadsense.routing import ROOT, fixture_fingerprint, slack_datetime

BRIEF_VERSION = 'agent3-morning-brief-v1'
RUN_ROOTS = (ROOT/'data/experiments',)
FIXTURE_RUN_ROOT = ROOT/'tests/fixtures/dashboard_runs'
# Files that make one immutable run instance; two directories can report the same run_id (same inputs).
INSTANCE_FILES = ('run_manifest.json', 'morning_brief.json', 'cards.json', 'review_queue.json')
# Decision namespace by run mode: only decisions on live runs are operational; scripted runs are demonstrations and
# the hand-written fixture runs are UI test data. Default snapshots ingest operational decisions only.
NAMESPACES = {'LIVE': 'operational', 'SCRIPTED': 'demo', 'TEST_FIXTURE': 'test', 'UNKNOWN': 'test'}
INCOMPLETE = ('TOPIC_FAILED', 'UNPROCESSED_BUDGET', 'UNPROCESSED_RUN_STOPPED', 'INTERRUPTED_UNCERTAIN')
SUPERSEDED_STATES = {'SUPERSEDED_REVISION', 'SECTION_SUPERSEDED'}


class RunNotFound(KeyError):
    pass


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def file_sha256(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run_mode(brief, manifest):
    if manifest.get('test_fixture'):
        return 'TEST_FIXTURE'
    return {'LIVE_MODEL': 'LIVE', 'SCRIPTED_MOCK': 'SCRIPTED'}.get(brief.get('semantic_judgments'), 'UNKNOWN')


def evidence_key(ref):
    """Ledger ID of a card citation (the note starts with it: 'k:...' or 'm:...')."""
    return (ref.get('note') or '').split(' ')[0] or None


def superseded_label(entry):
    """Visible label for evidence that is not current; None when it is current."""
    a, dates = entry.get('applicability') or {}, entry.get('dates') or {}
    if a.get('state') == 'SECTION_SUPERSEDED':
        by = ', '.join(f"{r['replaced_by']} (effective {r.get('replacement_effective')})" for r in a.get('replaced_by') or [])
        return f'Superseded section - replaced by {by}' if by else 'Superseded section'
    if a.get('state') == 'SUPERSEDED_REVISION' or a.get('revision_state') == 'SUPERSEDED_REVISION':
        return 'Superseded revision - a later version replaces it'
    if dates.get('expired_as_of'):
        return f"Expired - valid until {dates.get('valid_until')}"
    if a.get('state') and a['state'] not in ('CURRENT', 'UNRESOLVED'):
        return a['state'].replace('_', ' ').capitalize()
    return None


class Run:
    def __init__(self, path):
        self.path = Path(path)
        self.key = self.path.name
        self.brief = read_json(self.path/'morning_brief.json')
        self.manifest = read_json(self.path/'run_manifest.json')
        if self.brief.get('brief_version') != BRIEF_VERSION:
            raise ValueError(f'{self.key}: unsupported brief version {self.brief.get("brief_version")!r}.')
        self.mode = run_mode(self.brief, self.manifest)
        self.namespace = NAMESPACES[self.mode]
        self.cards_sha256 = file_sha256(self.path/'cards.json')
        # The binding for decisions and review actions: directory name plus the hash of its immutable files.
        self.instance = sha256(json.dumps({f: file_sha256(self.path/f) for f in INSTANCE_FILES}, sort_keys=True)
                               .encode('utf-8')).hexdigest()
        self.ref = f'{self.key}#{self.instance}'

    @cached_property
    def cards(self):
        """Every saved card, validated as AdviceCard v3 and returned unchanged."""
        cards = {}
        for raw in read_json(self.path/'cards.json'):
            AdviceCardV3.model_validate(raw)
            cards[raw['card_id']] = raw
        return cards

    @cached_property
    def brief_cards(self):
        return {c['card_id']: c for c in self.brief['cards']}

    @cached_property
    def topics(self):
        """card_id -> saved topic result (flat or the first version's nested topic paths)."""
        found = {}
        for path in sorted((self.path/'topics').rglob('*.json')):
            data = read_json(path)
            card_id = (data.get('workflow') or {}).get('card_id')
            if card_id:
                found[card_id] = data
        return found

    @cached_property
    def queue(self):
        return {raw['item_id']: ModelReviewItem.model_validate(raw) for raw in read_json(self.path/'review_queue.json')}

    def card(self, card_id):
        if card_id not in self.cards:
            raise RunNotFound(f'Card {card_id} is not in run {self.key}.')
        return self.cards[card_id]

    def semantic_source(self, card_id):
        if self.mode == 'TEST_FIXTURE':
            return 'TEST_FIXTURE'
        return self.brief_cards.get(card_id, {}).get('semantic_source')

    def summary(self, others=()):
        b, counts = self.brief, self.brief['counts']
        incomplete = b.get('incomplete_work') or []
        return {
            'run_key': self.key, 'run_id': b['run_id'], 'run_instance': self.instance, 'namespace': self.namespace,
            'mode': self.mode, 'status': b['status'], 'cutoff': b['cutoff'],
            'window': b['window'], 'semantic_judgments': b['semantic_judgments'], 'semantic_note': b['semantic_note'],
            'test_fixture_note': self.manifest.get('test_fixture_note'),
            'shares_run_id_with': sorted(o.key for o in others if o is not self and o.brief['run_id'] == b['run_id']),
            'projects': sorted({c['project_id'] for c in b['cards']}),
            'scope_only': (b.get('scope') or {}).get('only'),
            'cards': counts.get('cards', 0), 'cards_by_line': counts.get('cards_by_line', {}),
            'failed': sum(w['outcome'] == 'TOPIC_FAILED' for w in incomplete),
            'unprocessed': sum(w['outcome'] in INCOMPLETE[1:] for w in incomplete),
            'out_of_scope': len((b.get('scope') or {}).get('out_of_scope_work') or []),
            'review_queue_items': counts.get('review_queue_items', 0), 'cards_sha256': self.cards_sha256,
        }

    @cached_property
    def work_projects(self):
        """work_id -> project, from the run's member accounting (incomplete/out-of-scope entries omit it)."""
        return {m['work_id']: m['project_id'] for m in read_json(self.path/'accounting.json')['members'] if m.get('work_id')}

    def topic_summary(self):
        """One row per work item: processed (card), incomplete (failed/unprocessed) or out of scope."""
        rows = []
        for card in self.cards.values():
            topic = self.topics.get(card['card_id'], {})
            rows.append({'work_id': (topic.get('work_item') or {}).get('work_id'), 'topic_name': card['topic_name'],
                         'project_id': card['project_id'], 'outcome': (topic.get('workflow') or {}).get('outcome', 'CARD'),
                         'card_id': card['card_id'], 'card_line': card['card_line'],
                         'members': len(card['lineage']['member_ids'])})
        for w in self.brief.get('incomplete_work') or []:
            rows.append({'work_id': w['work_id'], 'topic_name': w.get('topic_name'), 'project_id': self.work_projects.get(w['work_id']),
                         'kind': w.get('kind'), 'outcome': w['outcome'], 'card_id': None, 'card_line': None, 'members': len(w.get('member_ids') or []),
                         'review_items_kept': len(w.get('obligations') or []), 'detail': w.get('detail') or w.get('error'),
                         'failure_class': w.get('failure_class')})
        for w in (self.brief.get('scope') or {}).get('out_of_scope_work') or []:
            rows.append({'work_id': w['work_id'], 'topic_name': w.get('topic_name'), 'project_id': self.work_projects.get(w['work_id']),
                         'kind': w.get('kind'), 'outcome': 'OUT_OF_SCOPE', 'card_id': None, 'card_line': None,
                         'members': w.get('members', len(w.get('member_ids') or []))})
        return rows

    def alternatives(self, card_id):
        """ToT alternatives the final grounding call judged SUPPORTED and SUFFICIENT, with no recorded prose or display
        issue (advisor_tot.check_candidates), other than the card's action."""
        result = (self.topics.get(card_id) or {}).get('result') or {}
        tot, grounding = result.get('tot') or {}, result.get('grounding') or {}
        judged = grounding.get('alternative_sufficiency') or {}
        statements = {s['statement_id']: s for s in grounding.get('statements') or []}
        shown = (self.cards[card_id].get('recommended_action') or {}).get('draft_text')
        out = []
        for c in tot.get('candidates') or []:
            sid = f"alternative:{c['candidate_id']}"
            j = judged.get(sid) or {}
            if j.get('check') != 'SUPPORTED' or j.get('verdict') != 'SUFFICIENT' or (statements.get(sid) or {}).get('verdict') != 'SUPPORTED':
                continue
            if c.get('issues') or c.get('draft_text') == shown:
                continue
            out.append({'candidate_id': c['candidate_id'], 'action_type': c['action_type'], 'label': ACTION_LABELS[c['action_type']],
                        'instruction': c.get('instruction'), 'draft_text': c.get('draft_text'), 'rationale': c.get('rationale'),
                        'preferred_by_comparison': c['candidate_id'] == tot.get('preferred_candidate_id')})
        return out

    def ledger(self, card_id):
        return ((self.topics.get(card_id) or {}).get('result') or {}).get('evidence_ledger') or {}

    def cited(self, card_id):
        card, keys = self.cards[card_id], []
        refs = [*card['supporting_sources'], *card['severity']['evidence'],
                *(e for m in card['severity']['matched_signals'] for e in m['evidence'])]
        for ref in refs:
            key = evidence_key(ref)
            if key and key not in keys:
                keys.append(key)
        return keys

    def cited_evidence(self, card_id):
        """Compact list of the card's cited sources, with the same not-current labels as the full view."""
        ledger, out = self.ledger(card_id), []
        for key in self.cited(card_id):
            entry = ledger.get(key)
            if entry is None:
                out.append({'evidence_id': key, 'missing_from_ledger': True})
                continue
            view = evidence_view(entry, cited=True)
            out.append({k: view[k] for k in ('evidence_id', 'origin', 'use', 'source_type', 'title', 'sections',
                                             'authoring', 'superseded_label', 'channel_id', 'thread_id', 'author_role')})
        return out

    def evidence(self, card_id):
        """Saved evidence for one card: every ledger entry, cited ones first, with labels for non-current sources."""
        cited = self.cited(card_id)
        entries = [evidence_view(e, cited=k in cited) for k, e in self.ledger(card_id).items()]
        return sorted(entries, key=lambda e: (not e['cited'], e['origin'] != 'retrieved_source', e['evidence_id']))

    def evidence_entry(self, evidence_id):
        for card_id in self.cards:
            entry = self.ledger(card_id).get(evidence_id)
            if entry is not None:
                return evidence_view(entry, cited=evidence_id in self.cited(card_id), full=True) | {'card_id': card_id}
        raise RunNotFound(f'Evidence {evidence_id} is not saved in run {self.key}.')

    def thread_keys(self):
        keys = set()
        for card_id, card in self.cards.items():
            keys |= {(t['channel_id'], t['thread_id']) for t in card['related_threads']}
            for e in self.ledger(card_id).values():
                source = (e.get('citation') or {}).get('source') or {}
                if e.get('channel_id') and e.get('thread_id'):
                    keys.add((e['channel_id'], e['thread_id']))
                elif source.get('system') == 'slack':
                    keys.add((source['channel_id'], source['thread_id']))
        return keys

    def saved_messages(self):
        """(channel, message ts) -> saved excerpt, for comparing the fixture thread with the run's evidence."""
        saved = {}
        for card_id in self.cards:
            for e in self.ledger(card_id).values():
                if e.get('origin') == 'member_message':
                    saved[(e['channel_id'], e['message_id'])] = e.get('excerpt')
        return saved


def evidence_view(entry, *, cited, full=False):
    citation = entry.get('citation') or {}
    source = citation.get('source') or {}
    is_message = entry.get('origin') == 'member_message'
    view = {
        'evidence_id': entry['evidence_id'], 'origin': entry.get('origin'), 'use': entry.get('use'), 'cited': cited,
        'source_type': 'slack_message' if is_message else entry.get('source_type'),
        'title': citation.get('title') if not is_message else f"Message by a {(entry.get('author_role') or 'participant').replace('_', ' ').lower()}",
        'authoring': citation.get('authoring'), 'sections': citation.get('sections') or [],
        'document_id': citation.get('document_id'), 'version_id': citation.get('version_id'),
        'chunk_id': citation.get('chunk_id'), 'source_system': 'slack' if is_message else source.get('system'),
        'channel_id': entry.get('channel_id') or source.get('channel_id'),
        'thread_id': entry.get('thread_id') or source.get('thread_id'),
        'message_id': entry.get('message_id') or source.get('message_id'),
        'permalink': source.get('permalink') or entry.get('permalink'),
        'author_role': entry.get('author_role'), 'author_id': entry.get('author_id'),
        'timestamp': entry.get('timestamp'), 'dates': entry.get('dates'), 'scope': entry.get('scope'),
        'applicability': entry.get('applicability'), 'authority': entry.get('authority'),
        'recorded_states': entry.get('recorded_states'), 'superseded_label': superseded_label(entry),
        'excerpt': entry.get('excerpt'),
    }
    if not full and view['excerpt'] and len(view['excerpt']) > 400:
        view['excerpt_preview'] = True
    return view


def thread_view(run, channel_id, thread_id, fixture_root=FIXTURE_ROOT):
    """Fixture thread (internal view; fixtures store no Slack permalinks), checked against the saved excerpts.

    fixture_status: VERIFIED_ORIGINAL when the fixture files match the fingerprint the run recorded; CHANGED_SINCE_RUN
    when they do not; NOT_RECORDED for runs that predate the fingerprint. Except when verified, messages are labelled
    current fixture content, separate from the run's saved evidence (each saved message is still compared).
    """
    if (channel_id, thread_id) not in run.thread_keys():
        raise RunNotFound(f'Thread {channel_id}/{thread_id} is not referenced by run {run.key}.')
    path = Path(fixture_root)/'channels'/f'{channel_id}.json'
    if not path.is_file():
        raise RunNotFound(f'Channel {channel_id} is not in the fixture.')
    data = read_json(path)
    users = {u['id']: u for u in read_json(Path(fixture_root)/'users.json')['users']}
    root = [m for m in data['history'] if m['ts'] == thread_id]
    if len(root) != 1:
        raise RunNotFound(f'Thread {thread_id} is not in channel {channel_id}.')
    saved = run.saved_messages()
    messages = []
    for m in [*root, *(r for r in data.get('replies', {}).get(thread_id, []) if r['ts'] != thread_id)]:
        excerpt = saved.get((channel_id, m['ts']))
        messages.append({'message_id': m['ts'], 'posted_at': slack_datetime(m['ts']).isoformat(),
                         'author_id': m.get('user'), 'author_role': (users.get(m.get('user')) or {}).get('role'),
                         'text': m.get('text', ''), 'permalink': m.get('permalink'),
                         'in_saved_evidence': excerpt is not None,
                         'matches_saved_evidence': None if excerpt is None else excerpt == m.get('text', '')})
    recorded = (run.manifest.get('fingerprints') or {}).get('fixture_sha256')
    status = 'NOT_RECORDED' if not recorded else 'VERIFIED_ORIGINAL' if recorded == fixture_fingerprint(fixture_root) \
        else 'CHANGED_SINCE_RUN'
    channel = data['channel']
    return {'fixture_status': status, 'fixture_sha256_recorded': recorded,'channel_id': channel_id, 'channel_name': channel.get('name'), 'project_id': channel.get('project_id'),
            'batch_id': channel.get('batch_id'), 'thread_id': thread_id, 'permalink': root[0].get('permalink'),
            'source': 'fixture', 'fixture_root': Path(fixture_root).resolve().relative_to(ROOT).as_posix()
            if Path(fixture_root).resolve().is_relative_to(ROOT) else str(fixture_root), 'messages': messages}


class Catalog:
    """Runs found under the given roots, keyed by directory name (unique; duplicates are refused)."""

    def __init__(self, roots=RUN_ROOTS, *, include_fixtures=False):
        self.roots = [Path(r) for r in roots] + ([FIXTURE_RUN_ROOT] if include_fixtures else [])
        self.runs = {}
        for root in self.roots:
            for path in sorted(root.glob('*/morning_brief.json')) if root.is_dir() else []:
                run = Run(path.parent)
                if run.key in self.runs:
                    raise ValueError(f'Two run directories are named {run.key}; give them distinct names.')
                self.runs[run.key] = run

    def get(self, key):
        if key not in self.runs:
            raise RunNotFound(f'No run {key}.')
        return self.runs[key]

    def summaries(self):
        order = {'LIVE': 0, 'SCRIPTED': 1, 'TEST_FIXTURE': 2}
        runs = sorted(self.runs.values(), key=lambda r: (order.get(r.mode, 3), r.key))
        return [r.summary(self.runs.values()) for r in runs]


def team_leads(fixture_root=FIXTURE_ROOT):
    """Fixture users recorded as team leads: the only actors who can record a TL decision."""
    return [{'actor_id': u['id'], 'name': u.get('name'), 'role': u['role']}
            for u in read_json(Path(fixture_root)/'users.json')['users'] if u.get('role') == 'TEAM_LEAD']
