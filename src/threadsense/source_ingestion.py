"""Zero-call source routing/extraction orchestration; durable JSON, no retrieval."""
from copy import deepcopy
from pathlib import Path

from threadsense.adapters.mock_slack import MockSlackAdapter
from threadsense.routing import IDENTITY, partition, select_activity
from threadsense.knowledge_sources import extract_announcement, store_source


def fixture_routes(fixture_root, *, cutoff=None, channels=None):
    root=Path(fixture_root)
    adapter=MockSlackAdapter(str(root/'channels'),str(root/'users.json'))
    ids=channels or sorted(p.stem for p in (root/'channels').glob('C_*.json'))
    sources=[s for channel in dict.fromkeys(ids) for s in adapter.get_source_threads(channel)]
    if cutoff is not None:
        selected,activity=select_activity(sources,cutoff)
    else:
        selected=sources
        activity={'window':None,'selection_mode':'complete_snapshot_not_daily',
            'source_threads_available':len(sources),'source_threads_in_window':len(sources),
            'source_messages_in_window':sum(len(s['messages']) for s in sources),
            'context_messages':0,'selection_failures':[]}
    discussion,announcements,routes=partition(selected)
    routes.update(activity)
    return discussion,announcements,routes


def extraction_report(discussion, announcements, routing, *, destination=None, canonical_members=()):
    """Dry-run validates records; write mode counts explicit independent outcomes."""
    by_identity={tuple(m[k] for k in IDENTITY):m for m in canonical_members}
    report=deepcopy(routing)
    report.update({'model_calls':0,'stored_new_records':0,'duplicate_records_skipped':0,
                   'stored_revisions':0,'validated_records':0,'extraction_failures':[],
                   'record_outcomes':[],'write':destination is not None})
    for thread in announcements:
        identity={k:thread.get(k) for k in IDENTITY}
        try:
            record=extract_announcement(thread,canonical_member=by_identity.get(tuple(identity.values())))
            outcome=store_source(record,destination) if destination is not None else {
                'status':'VALIDATED_NOT_STORED','document_id':record.record_id,'version_id':record.version_id}
            report['validated_records']+=1
            counter={'NEW':'stored_new_records','REVISION':'stored_revisions','DUPLICATE':'duplicate_records_skipped'}.get(outcome['status'])
            if counter:report[counter]+=1
            report['record_outcomes'].append({'identity':identity,**outcome})
        except (OSError,ValueError,KeyError,TypeError) as error:
            report['extraction_failures'].append({'identity':identity,'error':str(error),
                'source':deepcopy(thread),'inherited_agent1':deepcopy(by_identity.get(tuple(identity.values())))})
    assert len(discussion)+len(announcements)==report['input_threads']
    assert report['source_threads_in_window']==report['input_threads']+report.get('window_selection_failed_threads',0)
    assert report['validated_records']+len(report['extraction_failures'])==len(announcements)
    report['state']='complete_with_failures' if report['extraction_failures'] or report.get('selection_failures') else 'complete'
    return report


def interpretation_threads(fixture_root, *, cutoff=None, channels=None):
    discussion,announcements,routing=fixture_routes(fixture_root,cutoff=cutoff,channels=channels)
    adapter=MockSlackAdapter(str(Path(fixture_root)/'channels'),str(Path(fixture_root)/'users.json'))
    selected={(s['channel_id'],s['thread_id']):s for s in discussion}
    groups=[]
    for channel in dict.fromkeys(s['channel_id'] for s in discussion):
        group=[]
        for thread in adapter.get_threads(channel):
            raw=selected.get((thread.channel_id,thread.thread_id))
            if raw is None:continue
            # Convert the selected ingestion snapshot itself: reply_count may be
            # stale, and old get_threads callers historically trusted that hint.
            group.append(thread.model_copy(update={'messages':[adapter._convert_message(m) for m in raw['messages']]}))
        groups.append(group)
    threads=[group[i] for i in range(max(map(len,groups),default=0)) for group in groups if i<len(group)]
    assert len(threads)==len(discussion)
    return threads,announcements,routing


def existing_canonical_members():
    from threadsense.handoff_inputs import CANONICAL,load_handoff
    return load_handoff() if CANONICAL.exists() else []
