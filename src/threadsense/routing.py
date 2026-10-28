"""One deterministic channel boundary for ingestion, interpretation and grouping.

No text classification, authority inference, calls or retrieval. Historical loaders
can explicitly retain all inputs; prospective consumers use this partition.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CHANNEL_CONFIG = ROOT/'data/config/channel_routes.json'
ROUTING_VERSION = 'announcement-routing-v1'
IDENTITY = ('project_id', 'batch_id', 'channel_id', 'thread_id')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def aware(value):
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('An explicit timezone-aware timestamp is required.')
    return dt.astimezone(timezone.utc)


def slack_time(value):
    """Slack identifiers stay strings; exact decimal seconds, never floats."""
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d{1,6}', value):
        raise ValueError('Slack timestamp must be its original seconds.microseconds string.')
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError('Invalid Slack timestamp.') from None


def epoch(dt):
    delta = aware(dt)-datetime(1970,1,1,tzinfo=timezone.utc)
    return Decimal(delta.days*86400+delta.seconds)+Decimal(delta.microseconds)/1000000


def slack_datetime(value):
    return datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(microseconds=int(slack_time(value)*1000000))


def window(cutoff):
    end = aware(cutoff)
    return {'start': (end-timedelta(hours=24)).isoformat(), 'cutoff': end.isoformat(),
            'interval': '[start, cutoff)'}


def source_of(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump(mode='json')
    return value.get('original_thread', value)


def channel_rules(path=CHANNEL_CONFIG):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data['version'] != ROUTING_VERSION:
        raise ValueError('Unsupported routing configuration.')
    return data['channels']


def route_kind(value, *, rules=None):
    source = source_of(value)
    rules = channel_rules() if rules is None else rules
    configured = rules.get(source['channel_id'])
    recorded = source.get('channel_type')
    if configured:
        if recorded is not None and recorded != configured['channel_type']:
            raise ValueError('Configured and recorded channel types conflict.')
        if source.get('project_id') is not None and configured.get('project_id') not in (None, source['project_id']):
            raise ValueError('Configured channel/project scope conflicts with source.')
        recorded = configured['channel_type']
    if recorded == 'ANNOUNCEMENTS':
        return 'ANNOUNCEMENT'
    if recorded in {'GENERAL', 'QA', 'TUTOR'}:
        return 'DISCUSSION'
    raise ValueError('Channel needs an explicit ID/type configuration; no name/text inference.')


def partition(values, *, rules=None):
    """Preserve every identity, source and flag in exactly one primary route."""
    rules = channel_rules() if rules is None else rules
    discussion, announcements, entries, seen = [], [], [], set()
    for value in values:
        src = source_of(value)
        identity = {k:src.get(k) for k in IDENTITY}
        key = tuple(identity.values())
        if key in seen:
            raise ValueError('Duplicate full routing identity.')
        seen.add(key)
        kind = route_kind(value, rules=rules)
        (announcements if kind=='ANNOUNCEMENT' else discussion).append(value)
        entries.append({'identity':identity,'route':kind,'input_sha256':digest(value.model_dump(mode='json') if hasattr(value,'model_dump') else value)})
    manifest = {'routing_version':ROUTING_VERSION,'rules_sha256':digest(rules),
        'input_threads':len(values),'eligible_threads':len(discussion),
        'announcement_threads':len(announcements),'entries':entries,
        'announcement_sources':[deepcopy(v.model_dump(mode='json') if hasattr(v,'model_dump') else v) for v in announcements],
        'mirrored_decisions':0}
    assert len(discussion)+len(announcements)==len(values)==len(seen)
    return discussion, announcements, manifest


def require_discussion(value):
    if route_kind(value) != 'DISCUSSION':
        raise ValueError('Announcement-channel source must use knowledge extraction, not interpretation/clustering.')


def select_activity(threads, cutoff):
    """Select creations or exposed last edits in [cutoff-24h, cutoff).

    Keeps older parent/context messages. Reactions have no event timestamps in
    these fixtures; reaction-only activity and unavailable edit history are not
    claimed. A post-cutoff edited snapshot cannot be represented as older evidence.
    """
    bounds=window(cutoff); start,end=epoch(bounds['start']),epoch(bounds['cutoff'])
    selected=[]; failures=[]; activity_count=0; context_count=0
    for thread in threads:
        messages=thread['messages']; active=[]; visible=[]
        try:
            for message in messages:
                created=slack_time(message['ts'])
                edited=message.get('edited', {}).get('ts') if isinstance(message.get('edited'),dict) else None
                changed=slack_time(edited) if edited is not None else None
                if start<=created<end or (changed is not None and start<=changed<end):
                    active.append(message['ts'])
                if created<end:
                    visible.append(message)
            if not active:
                continue
            if any(isinstance(m.get('edited'),dict) and m['edited'].get('ts') and end<=slack_time(m['edited']['ts']) for m in visible):
                raise ValueError('Source snapshot edited at/after cutoff; prior content unavailable.')
            item=deepcopy(thread);item['messages']=deepcopy(visible)
            item['active_message_ids']=active;item['extraction_window']=bounds
            context_count+=len(visible)-len(active)
            selected.append(item)
        except (ValueError, KeyError, TypeError) as error:
            failures.append({'identity':{k:thread.get(k) for k in IDENTITY},
                'known_activity_in_window':bool(active),
                'stage':'activity_selection','error':str(error),'source':deepcopy(thread)})
        finally:
            activity_count+=len(active)
    return selected, {'window':bounds,'source_threads_available':len(threads),
        'source_threads_in_window':len(selected)+sum(f['known_activity_in_window'] for f in failures),
        'window_selection_failed_threads':sum(f['known_activity_in_window'] for f in failures),
        'unclassified_source_threads':sum(not f['known_activity_in_window'] for f in failures),
        'outside_window_threads':len(threads)-len(selected)-len(failures),
        'source_messages_in_window':activity_count,
        'context_messages':context_count,'selection_failures':failures,
        'limitations':['Only supplied creation and last-edit timestamps are observable.',
                      'Reaction-only activity and missing/deleted edit history are not observable.']}
