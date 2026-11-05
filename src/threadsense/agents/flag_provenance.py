"""Flag provenance and card dependencies for saved Agent 3 runs (read-only, zero calls).

FlagSource(run_dir, run_ref) opens the handoff the run recorded (run_manifest fingerprints.handoff: path, canonical and
routing-manifest hashes) and refuses one that changed since. provenance(card) recovers the upstream finding behind every
inherited flag: Agent 1's verification artifact (lineage verification_file under the recorded lineage base, checked as
handoff_inputs.load_handoff checks it), Agent 1 content reviews, and Agent 2 content cautions. Only the findings of the
attempt Agent 1 kept are findings. A substantive finding of the discarded attempt is a PriorFinding whose status is read
from the recorded values (OPEN, CORRECTED, SUPERSEDED or UNCERTAIN; see advice_contracts.PriorFinding); its process
failures, the attempt's own error and a failed revision are AttemptErrors. Nothing is guessed: a missing or changed
artifact is UNAVAILABLE, and a check that failed without naming fields is NOT_NARROWED.

dependencies(card, result, provenance) traces the disputed fields and messages through the saved card: the grounding
statements (the text a card may display, with their evidence), summary-sentence and action-premise claim links, member
and topic resolution, severity, the title and the first retrieval query. It establishes references, never independence:
whether a reference changes the card is a semantic judgment, kept as human assessments in
data/evaluation/agent3_flag_dependence_labels_v1.json.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

from threadsense.agents.advice_contracts import (GROUPING_LABEL, AttemptError, CardDependencies, DependencyLink,
                                                 FlagProvenanceV2 as FlagProvenance, PriorFinding, ResolutionInput,
                                                 SourceArtifact, UpstreamFinding)
from threadsense.agents.advisor_checks import topic_resolution
from threadsense.agents.verification_handoff import digest
from threadsense.routing import ROOT

# Prefixes verification_pipeline.check() gives a finding when the check itself failed; such a finding names every
# interpretation field and no message, so it does not narrow the dispute.
PROCESS_FAILURES = ('Independent evidence audit unavailable or invalid: ', 'Deterministic verification failed: ',
                    'Invalid interpretation schema: ')
REVISION_FAILED = 'The single targeted revision failed: '
STILL_UNVERIFIED = 'Still unverified after one targeted revision: '
# interpretation_verifier's coverage finding names the state independent coverage establishes.
# Fields whose recorded value settles a finding when it changes; a rewritten prose field (summary, central question,
# rationale) may still carry the disputed claim, so a change there plus a silent re-check is not a correction.
STRUCTURED = {'resolution_state', 'authoritative_response_present', 'authority_evidence_message_ids', 'confidence'}
COVERAGE = re.compile(r'Independent decision coverage establishes (UNRESOLVED|PARTIALLY_RESOLVED|RESOLVED_IN_THREAD);')
RESOLUTION_FIELDS = {'resolution_state', 'resolution_rationale'}
REAL_STATES = ('UNRESOLVED', 'PARTIALLY_RESOLVED', 'RESOLVED_IN_THREAD')
LABELS = {'inherited_agent1_review': 'Agent 1 interpretation not verified',
          'inherited_agent1_review_announcement_route': 'Agent 1 interpretation not verified (announcement route)',
          'assisted_content_review': 'Content review caution', 'projection_gap': GROUPING_LABEL}
# Detail sentences (draft v11) are summary-level prose and the NO_ACTION reason is the action's rationale: they reuse
# those element kinds (CardDependencies v1 unchanged); element_id keeps them apart.
ELEMENTS = (('claim:', 'CLAIM'), ('summary', 'SUMMARY'), ('detail:', 'SUMMARY'), ('action:rationale', 'ACTION_RATIONALE'),
            ('action:no_action', 'ACTION_RATIONALE'),
            ('action:need', 'ACTION_NEED'), ('action', 'ACTION'), ('severity', 'SEVERITY'), ('reporter:', 'REPORTER'),
            ('review_note', 'REVIEW_NOTE'), ('resolution:', 'MEMBER_RESOLUTION'), ('alternative:', 'ALTERNATIVE'),
            ('open_question', 'OPEN_QUESTION'))


def _file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _shown_path(path):
    path = Path(path)
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path).replace('\\', '/')


@lru_cache(maxsize=4)
def _bound_view(run, canonical, routing):
    from threadsense.agents.advice_inputs import load_effective_view
    handoff = ROOT/run
    view = load_effective_view(handoff)
    if view['canonical_sha256'] != canonical:
        raise ValueError(f'{run} canonical output changed since the run.')
    if _file_hash(handoff/'routing_manifest.json') != routing:
        raise ValueError(f'{run} routing manifest changed since the run.')
    members = {m['member_id']: m for row in view['records'] for m in row['members']}
    return view, {row['candidate_group_id']: row for row in view['records']}, members


class FlagSource:
    """One run's binding to its handoff; every flag on its cards is resolved through it."""

    def __init__(self, run_dir, run_ref):
        self.path, self.ref = Path(run_dir), run_ref
        manifest = json.loads((self.path/'run_manifest.json').read_text(encoding='utf-8'))
        self.queue = json.loads((self.path/'review_queue.json').read_text(encoding='utf-8'))
        binding = (manifest.get('fingerprints') or {}).get('handoff') or {}
        self.records, self.members, self.error = {}, {}, None
        if not all(binding.get(k) for k in ('run', 'canonical_sha256', 'routing_manifest_sha256')):
            self.error = 'The run did not record its handoff binding.'
            return
        try:
            _, self.records, self.members = _bound_view(binding['run'], binding['canonical_sha256'],
                                                        binding['routing_manifest_sha256'])
        except (OSError, ValueError, KeyError) as error:
            self.error = f'Bound handoff not usable ({type(error).__name__}: {error}).'

    @classmethod
    def from_view(cls, view, run_ref):
        """A source over an already loaded handoff (an in-flight topic): no run queue yet, so no queue item IDs."""
        self = cls.__new__(cls)
        self.path, self.ref, self.queue, self.error = None, run_ref, [], None
        self.records = {row['candidate_group_id']: row for row in view['records']}
        self.members = {m['member_id']: m for row in view['records'] for m in row['members']}
        return self

    def provenance(self, card):
        return [self._flag(card, i, f) for i, f in enumerate(card.get('inherited_flags') or [])]

    def _queue_item(self, flag):
        for item in self.queue:
            if ((item['origin'], item['kind'], item['candidate_group_id'], item.get('obligation_id'))
                    == (flag['origin'], flag['kind'], flag['candidate_group_id'], flag.get('obligation_id'))
                    and set(flag.get('member_ids') or []) <= set(item.get('member_ids') or [])):
                return item['item_id']
        return None

    def _flag(self, card, index, flag):
        gid = flag['candidate_group_id']
        base = {'run_ref': self.ref, 'card_id': card['card_id'], 'flag_index': index, 'origin': flag['origin'],
                'kind': flag['kind'], 'candidate_group_id': gid, 'member_ids': flag.get('member_ids') or [],
                'obligation_id': flag.get('obligation_id'), 'card_detail': flag.get('detail'),
                'label': LABELS.get(flag['kind'], flag['kind'].replace('_', ' '))}
        if flag['kind'] == 'projection_gap':
            return FlagProvenance(**base, category='TOPIC_GROUPING', recovery='NOT_APPLICABLE', card_detail_is='GROUPING_NOTE',
                                  recovery_note='A card-only grouping condition: no Model Review Queue item; counted in '
                                                'the run accounting as a projection gap.')
        base['queue_item_id'] = self._queue_item(flag)
        if flag['origin'] == 'assisted_content_review':
            base.update(category='CONTENT_CAUTION', obligation_key=f"content:{flag['obligation_id']}")
            return self._caution(base, flag) if not self.error else FlagProvenance(**base, recovery='UNAVAILABLE',
                                                                                   recovery_note=self.error)
        if flag['origin'] == 'agent1':
            base.update(category='UPSTREAM_REVIEW', obligation_key=f"agent1:{flag['member_ids'][0]}")
            return self._agent1(base, flag) if not self.error else FlagProvenance(**base, recovery='UNAVAILABLE',
                                                                                 recovery_note=self.error)
        base.update(category='UPSTREAM_REVIEW', obligation_key=f"agent2:{gid}:{flag['kind']}")
        return FlagProvenance(**base, recovery='UNAVAILABLE',
                              recovery_note=f"Provenance for the Agent 2 obligation kind {flag['kind']} is not implemented.")

    def _caution(self, base, flag):
        row = self.records.get(flag['candidate_group_id']) or {}
        obligation = next((o for o in row.get('content_review_obligations', [])
                           if o['obligation_id'] == flag['obligation_id']), None)
        if obligation is None:
            return FlagProvenance(**base, recovery='UNAVAILABLE', recovery_note='The bound handoff has no matching caution.')
        finding, origin = obligation.get('finding') or {}, (obligation.get('provenance') or [{}])[0]
        text = ' '.join(x for x in (finding.get('summary'), finding.get('detail')) if x)
        source = SourceArtifact(path=_shown_path(origin['file']) if origin.get('file') else 'carried review supplement',
                                pointer=origin.get('pointer'), sha256=origin.get('sha256'))
        found = UpstreamFinding(origin='agent2_content_caution', category=finding.get('kind') or 'CONTENT_CAUTION',
                                nature='SUBSTANTIVE', disputed_fields=list(finding.get('affected_fields') or []),
                                member_ids=[e['member_id'] for e in finding.get('canonical_member_evidence') or []],
                                explanation=text, source=source)
        return FlagProvenance(**base, findings=[found], recovery='RECOVERED',
                              card_detail_is='FINDING' if flag.get('detail') and flag['detail'] in text else 'UNMATCHED')

    def _agent1(self, base, flag):
        mid = flag['member_ids'][0]
        member, row = self.members.get(mid), self.records.get(flag['candidate_group_id']) or {}
        if member is None or not any(o['member_id'] == mid for o in row.get('inherited_review_obligations', [])):
            return FlagProvenance(**base, recovery='UNAVAILABLE', recovery_note='The bound handoff has no matching Agent 1 obligation.')
        record = member['agent1_record']
        lineage, channel = record['lineage'], record['channel_id']
        root = Path(member['agent1_lineage_base'])
        path = (root/lineage['verification_file']).resolve()
        try:
            if not path.is_relative_to((root/'records').resolve()):
                raise ValueError('reference escapes the records directory')
            saved = json.loads(path.read_text(encoding='utf-8-sig'))
            if saved.get('result_sha256') != digest(saved.get('result')):
                raise ValueError('result checksum mismatch')
            if saved['result']['interpretation'] != record['interpretation']:
                raise ValueError('kept interpretation differs from the handoff record')
        except (OSError, ValueError, KeyError) as error:
            return FlagProvenance(**base, recovery='UNAVAILABLE', recovery_note=f'Agent 1 verification artifact not usable '
                                  f'({type(error).__name__}: {error}); the finding was not recovered.')
        result, sha, shown = saved['result'], _file_hash(path), _shown_path(path)
        effective = result.get('effective_attempt') or lineage.get('effective_attempt') or 'original'
        findings, errors, history, discarded = [], [], [], []
        passes = result.get('passes') or []
        kept_fields = {d for p in passes if ('original' if p['number'] == 1 else 'revision') == effective
                       for item in p.get('findings') or [] for d in item.get('disputed_fields') or []}
        for n, attempt_pass in enumerate(passes):
            attempt = 'original' if attempt_pass['number'] == 1 else 'revision'
            source = SourceArtifact(path=shown, pointer=f'/result/passes/{n}/findings', sha256=sha)
            for item in attempt_pass.get('findings') or []:
                found = _finding('agent1_verification', attempt, item, channel, mid, source)
                if attempt != effective:
                    discarded.append(item['explanation'])
                if attempt == effective:
                    findings.append(found)
                elif found.nature == 'PROCESS_FAILURE':
                    errors.append(AttemptError(stage='NON_EFFECTIVE_ATTEMPT', attempt=attempt, text=item['explanation'],
                                               source=source))
                else:
                    history.append(_prior(found, item, attempt, attempt_pass.get('interpretation'),
                                          result.get('interpretation'), kept_fields))
            # The attempt's own error, unless a process-failure finding already carries it.
            if attempt != effective and attempt_pass.get('error') and not any(
                    str(attempt_pass['error']) in item['explanation'] for item in attempt_pass.get('findings') or []):
                errors.append(AttemptError(stage='NON_EFFECTIVE_ATTEMPT', attempt=attempt, text=str(attempt_pass['error']),
                                           source=SourceArtifact(path=shown, pointer=f'/result/passes/{n}/error', sha256=sha)))
        if result.get('revision_error'):
            errors.append(AttemptError(stage='REVISION_FAILED', attempt='revision', text=REVISION_FAILED + result['revision_error'],
                                       source=SourceArtifact(path=shown, pointer='/result/revision_error', sha256=sha)))
        for review in record.get('content_reviews') or []:
            if review.get('needs_review'):
                origin = review.get('provenance') or {}
                source = SourceArtifact(path=origin.get('review_file') or 'Agent 1 content review',
                                        pointer=origin.get('review_pointer'), sha256=origin.get('review_file_sha256'))
                findings += [_finding('agent1_content_review', effective, item, channel, mid, source)
                             for item in review.get('findings') or []]
        if any(f.nature == 'SUBSTANTIVE' for f in findings):
            recovery, note = 'RECOVERED', None
        elif findings:
            recovery, note = 'NOT_NARROWED', ("The kept attempt's check failed without naming a disputed field or message; "
                                              'every interpretation field stays provisional.')
        else:
            recovery, note = 'UNAVAILABLE', 'The artifact records no finding for the kept attempt.'
        return FlagProvenance(**base, effective_attempt=effective, findings=findings, attempt_errors=errors,
                              finding_history=history, recovery=recovery, recovery_note=note,
                              card_detail_is=_detail_kind(flag.get('detail'), findings, errors,
                                                          discarded))


def _finding(origin, attempt, item, channel, member_id, source):
    text = item['explanation']
    return UpstreamFinding(origin=origin, attempt=attempt, category=item.get('category') or 'UNSPECIFIED',
                           nature='PROCESS_FAILURE' if text.startswith(PROCESS_FAILURES) else 'SUBSTANTIVE',
                           disputed_fields=list(item.get('disputed_fields') or []),
                           message_ids=[f'm:{channel}:{m}' for m in item.get('evidence_message_ids') or []],
                           member_ids=[member_id], explanation=text, source=source)


def _prior(found, item, attempt, values, kept, kept_fields):
    """What the record establishes about one substantive finding of the discarded attempt (PriorFinding)."""
    fields = list(item.get('disputed_fields') or [])
    if not fields or values is None or kept is None:
        return PriorFinding(finding=found, status='UNCERTAIN', basis='The record does not show which values the finding '
                            'disputed or which values were kept.')
    changed = [f for f in fields if values.get(f) != kept.get(f)]
    unchanged = [f for f in fields if f not in changed]
    target = COVERAGE.match(found.explanation)
    target = target[1] if target else None
    out = {'finding': found, 'changed_fields': changed, 'unchanged_fields': unchanged}
    if target and kept.get('resolution_state') != target:
        return PriorFinding(**out, status='OPEN', basis=f'Independent coverage established {target}; the kept '
                            f"interpretation reports {kept.get('resolution_state')}.")
    if attempt == 'original':  # The revision was kept.
        if set(fields) & kept_fields:
            return PriorFinding(**out, status='SUPERSEDED', basis="The kept revision's check disputes the same fields "
                                f'again ({", ".join(sorted(set(fields) & kept_fields))}); that finding is open.')
        if (target and set(fields) <= {'resolution_state', 'resolution_rationale'}) or (not unchanged and set(fields) <= STRUCTURED):
            note = f' and now holds the state coverage established ({target})' if target else ''
            kept_text = f'; {", ".join(unchanged)} unchanged' if unchanged else ''
            return PriorFinding(**out, status='CORRECTED', basis=f'The kept revision changed {", ".join(changed)}{note}'
                                f"{kept_text}, and the revision's check raised no finding on them.")
        if unchanged:
            return PriorFinding(**out, status='UNCERTAIN', basis=f'The kept revision left {", ".join(unchanged)} unchanged '
                                'and its check did not dispute them again; a later check accepting an unchanged value does '
                                'not establish that the earlier finding was wrong.')
        return PriorFinding(**out, status='UNCERTAIN', basis=f'The kept revision rewrote {", ".join(changed)} and its check '
                            'raised nothing on them, but rewritten prose may still carry the disputed claim; the record '
                            'does not establish a correction.')
    if unchanged:  # The revision was discarded: what it shares with the kept original is still disputed.
        return PriorFinding(**out, status='OPEN', basis=f'The discarded revision holds the kept values for '
                            f'{", ".join(unchanged)}; the finding applies to the kept interpretation.')
    note = f'; the kept interpretation already holds the state coverage established ({target})' if target else ''
    return PriorFinding(**out, status='SUPERSEDED', basis=f'It disputes values only the discarded revision held '
                        f'({", ".join(changed)}){note}.')


def _detail_kind(detail, findings, errors, prior=()):
    """Which recorded text the card's saved flag detail repeats (Agent 1's review_reason)."""
    if not detail:
        return None
    kept = [f.explanation for f in findings]
    checked = [f.explanation for f in findings if f.origin == 'agent1_verification']
    other = [e.text for e in errors if e.stage == 'NON_EFFECTIVE_ATTEMPT']
    if detail in kept or detail in ('; '.join(kept), STILL_UNVERIFIED + '; '.join(checked)):
        return 'FINDING'
    if detail in [e.text for e in errors] or (other and detail == STILL_UNVERIFIED + '; '.join(other)):
        return 'ATTEMPT_ERROR'
    if prior and detail in (STILL_UNVERIFIED + '; '.join(prior), '; '.join(prior)):
        return 'ATTEMPT_ERROR'  # The discarded attempt's finding texts (finding_history holds their status).
    return 'UNMATCHED'


def _element(statement_id):
    return next((e for prefix, e in ELEMENTS if statement_id.startswith(prefix)), 'OTHER')


def dependencies(card, result, prov, source=None):
    """References between one flag's disputed fields/messages and the card's elements (see the module docstring)."""
    out = {'run_ref': prov.run_ref, 'card_id': prov.card_id, 'flag_index': prov.flag_index}
    if prov.category == 'TOPIC_GROUPING':
        return CardDependencies(**out, links=[
            DependencyLink(element='TOPIC_MEMBERSHIP', element_id='lineage.member_ids', relation='DIRECT', displayed=True,
                           note='Every card element is computed over this projected group, which has no Agent 2 topic.'),
            DependencyLink(element='TITLE', element_id='title', relation='DIRECT', displayed=True,
                           note='The saved topic name is a mechanical label; the dashboard shows "Threads awaiting a topic".')])
    if result is None:
        return CardDependencies(**out, record_gaps=['The run saved no topic result for this card.'])
    links, gaps = [], []
    if prov.category == 'CONTENT_CAUTION':
        _caution_links(card, prov, source, links, gaps)
        return CardDependencies(**out, links=links, record_gaps=gaps)
    ledger = result.get('evidence_ledger') or {}
    draft = (result.get('drafts') or {}).get('final') or {}
    statements = (result.get('grounding') or {}).get('statements') or []
    # Saved statements carry their final verdict; proposed ones (an in-flight grounding request) are candidates.
    shown = {s['statement_id']: s.get('verdict', 'SUPPORTED') == 'SUPPORTED' for s in statements}
    members = set(prov.member_ids)
    thread = {e for e, v in ledger.items() if v.get('member_id') in members}
    narrowed = prov.recovery == 'RECOVERED'
    # Every unresolved finding counts: the kept attempt's and the discarded attempt's OPEN or UNCERTAIN ones.
    substantive = [f for f in prov.open_findings() if f.nature == 'SUBSTANTIVE']
    disputed = {m for f in substantive for m in f.message_ids}
    fields = {d for f in substantive for d in f.disputed_fields}
    loose = 'NOT_ESTABLISHED'
    hit_claims, loose_claims = {}, {}
    for s in statements:
        sid, cited = s['statement_id'], set(s.get('evidence_ids') or [])
        if sid.startswith('resolution:'):
            continue
        if narrowed and cited & disputed:
            links.append(DependencyLink(element=_element(sid), element_id=sid, relation='DIRECT', displayed=shown[sid],
                                        via=sorted(cited & disputed), note='Cites a message the finding names (' +
                                        ', '.join(sorted(fields)) + '); whether it adopts the disputed reading is semantic.'))
            if sid.startswith('claim:'):
                hit_claims[sid[6:]] = sorted(cited & disputed)
        elif cited & thread:
            relation = 'SAME_THREAD' if narrowed else loose
            links.append(DependencyLink(element=_element(sid), element_id=sid, relation=relation, displayed=shown[sid],
                                        via=sorted(cited & thread), note=(
                                            'Cites the flagged thread but no message the finding names; not a dependence '
                                            'by itself.' if narrowed else 'Cites the flagged thread; the dispute is not '
                                            'narrowed to fields or messages.')))
            if not narrowed and sid.startswith('claim:'):
                loose_claims[sid[6:]] = sorted(cited & thread)
    traced = {l.element_id for l in links}

    def through(claim_ids, element, element_id, displayed, label):
        if element_id in traced:  # Already linked through its own cited evidence.
            return
        for claims, relation in ((hit_claims, 'DERIVED'), (loose_claims, loose)):
            via = [f'claim:{c}' for c in claim_ids if c in claims]
            if via:
                links.append(DependencyLink(element=element, element_id=element_id, relation=relation, displayed=displayed,
                                            via=via, note=f'{label} rests on {", ".join(via)}.'))
                return
    sentences = draft.get('summary_sentences')
    if sentences:
        for n, sentence in enumerate(sentences, 1):
            sid = f'summary:s{n}'
            through(sentence.get('support_claim_ids') or [], 'SUMMARY', sid, shown.get(sid, False), 'This summary sentence')
    elif 'summary' in shown:
        gaps.append('This run records no sentence-to-claim links; the summary is traced through its cited evidence only.')
    for n, sentence in enumerate(draft.get('detail_sentences') or [], 1):  # Draft v11: the opened card's details.
        sid = f'detail:d{n}'
        through(sentence.get('support_claim_ids') or [], 'SUMMARY', sid, shown.get(sid, False), 'This detail sentence')
    action, proposed = card.get('recommended_action'), draft.get('proposed_action') or {}
    if action and action['action_type'] != 'NO_ACTION':
        if result.get('action_source') == 'DRAFT' and proposed.get('action_type') == action['action_type']:
            through(proposed.get('support_claim_ids') or [], 'ACTION_PREMISE', 'action', True, 'The action (instruction, scope, draft)')
            through(proposed.get('context_claim_ids') or [], 'ACTION_CONTEXT', 'action:context', True, 'The action context')
        else:
            gaps.append('The displayed action is not the final draft\'s proposal; its premise links are not recorded here.')
    if not any(s['statement_id'].startswith('severity') for s in statements):
        for n, signal in enumerate(card['severity'].get('matched_signals') or []):
            notes = {(e.get('note') or '').split(' ')[0] for e in signal.get('evidence') or []}
            if narrowed and notes & disputed:
                links.append(DependencyLink(element='SEVERITY', element_id=f'severity.matched_signals[{n}]', relation='DIRECT',
                                            displayed=True, via=sorted(notes & disputed), note='The signal cites a message the finding names.'))
    inputs, topic = _resolution(card, result, prov, fields, narrowed, shown, links, gaps)
    _query(result, prov, source, fields, narrowed, links)
    links.append(_draft_input(result, prov))
    return CardDependencies(**out, links=links, topic_resolution=topic, resolution_inputs=inputs, record_gaps=gaps)


def _resolution(card, result, prov, fields, narrowed, shown, links, gaps):
    saved = result.get('resolution') or {}
    states, topic = saved.get('members') or {}, saved.get('topic')
    order = list(card['lineage'].get('member_ids') or states)
    if not states:
        gaps.append('The run saved no member resolution states.')
        return [], topic
    current = topic_resolution(order, states)
    inputs = [ResolutionInput(member_id=m, state=states.get(m, 'UNKNOWN'), flagged=m in prov.member_ids,
                              states_changing_topic=[s for s in REAL_STATES if s != states.get(m)
                                                     and topic_resolution(order, {**states, m: s}) != current])
              for m in order]
    if current != topic:
        gaps.append(f'The saved topic state {topic} does not follow from the saved member states ({current}).')
    for entry in inputs:
        if not entry.flagged:
            continue
        sid = f'resolution:{entry.member_id}'
        if narrowed and fields & RESOLUTION_FIELDS:
            relation, note = 'DIRECT', f'Assesses the field the finding disputes; the card records {entry.state}.'
        elif narrowed:
            relation, note = 'SAME_THREAD', 'Assesses the flagged thread; the finding disputes other fields.'
        else:
            relation, note = 'NOT_ESTABLISHED', 'Assesses the flagged thread; the dispute is not narrowed.'
        links.append(DependencyLink(element='MEMBER_RESOLUTION', element_id=sid, relation=relation,
                                    displayed=shown.get(sid, False), note=note))
        if relation == 'SAME_THREAD':
            continue
        if entry.state != 'UNKNOWN':
            links.append(DependencyLink(element='THREAD_STATUS', element_id='thread_status',
                                        relation='DERIVED' if relation == 'DIRECT' else 'NOT_ESTABLISHED', displayed=True,
                                        via=[sid], note=f"The card's thread-status counts include this member's state "
                                                        f'({entry.state}).'))
        if current != topic:
            links.append(DependencyLink(element='TOPIC_RESOLUTION', element_id='topic_resolution', relation='NOT_ESTABLISHED',
                                        displayed=True, via=[sid], note='Saved topic state not reproducible from member states.'))
        elif entry.states_changing_topic:
            links.append(DependencyLink(element='TOPIC_RESOLUTION', element_id='topic_resolution',
                                        relation='DERIVED' if relation == 'DIRECT' else 'NOT_ESTABLISHED', displayed=True, via=[sid],
                                        note=f'The topic state {topic} changes if this member were '
                                             f'{" or ".join(entry.states_changing_topic)}.'))
        else:
            links.append(DependencyLink(element='TOPIC_RESOLUTION', element_id='topic_resolution', relation='INVARIANT',
                                        displayed=True, via=[sid], note=f'The topic state {topic} is the same for every state '
                                                                         'of this member.'))
    return inputs, topic


def _draft_input(result, prov):
    """Whether the recorded draft request carried this member's Agent 1 interpretation (summary, central question,
    resolution label). Runs before the context was recorded cannot say."""
    sent = [c for c in result.get('agent1_context') or []
            if any(i.get('member_id') in prov.member_ids for i in c.get('content') or [])]
    if not sent:
        return DependencyLink(element='DRAFT_INPUT', element_id='agent1_interpretations', relation='NOT_ESTABLISHED',
                              displayed=False, note="The run did not record the Agent 1 context sent to drafting, so "
                                                    "whether this member's interpretation was in the request is not recorded.")
    return DependencyLink(element='DRAFT_INPUT', element_id='agent1_interpretations', relation='DIRECT', displayed=False,
                          via=[c['sha256'] for c in sent],
                          note="The recorded draft context carried this member's Agent 1 summary, central question and "
                               "resolution label (marked 'not evidence'); whether the draft used them is semantic.")


def _query(result, prov, source, fields, narrowed, links):
    member = (source.members if source else {}).get(prov.member_ids[0]) if prov.member_ids else None
    question = ((member or {}).get('agent1_record') or {}).get('interpretation', {}).get('central_question')
    query = (result.get('topic') or {}).get('initial_query') or ''
    if question and question in query and (not narrowed or 'central_question' in fields):
        links.append(DependencyLink(element='RETRIEVAL_QUERY', element_id='topic.initial_query',
                                    relation='DIRECT' if narrowed else 'NOT_ESTABLISHED', displayed=False,
                                    note="The first retrieval query used this member's Agent 1 central question"
                                         + (', which the finding disputes.' if narrowed else '; the dispute is not narrowed.')))


def _caution_links(card, prov, source, links, gaps):
    row = (source.records if source else {}).get(prov.candidate_group_id) or {}
    for field in sorted({d for f in prov.findings for d in f.disputed_fields}):
        match = re.fullmatch(r'topics\[(\d+)\]\.topic_name', field)
        topics = row.get('topics') or []
        if match and int(match[1]) < len(topics) and topics[int(match[1])].get('topic_id') == card['lineage'].get('topic_id'):
            links.append(DependencyLink(element='TITLE', element_id='title', relation='DIRECT', displayed=True,
                                        via=[field], note=f'The caution disputes the displayed title "{card["topic_name"]}".'))
            links.append(DependencyLink(element='SUMMARY', element_id='summary', relation='NOT_ESTABLISHED', displayed=True,
                                        note='Whether other card text repeats the disputed naming is a semantic question; '
                                             'the records link the caution to the title only.'))
        else:
            gaps.append(f'The caution field {field} could not be matched to an element of this card.')
