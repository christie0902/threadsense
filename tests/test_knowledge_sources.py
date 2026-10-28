"""Synthetic document content lives only in temporary test directories."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from threadsense.knowledge_sources import SourceRecord, extract_announcement, store_source, normalize_document, iter_documents
from tests.test_announcement_routing import source, reply


def write(path,record):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(record.model_dump() if isinstance(record,SourceRecord) else record),encoding='utf-8')
    return path


def test_roles_replies_reactions_and_unknown_authority_are_preserved():
    s=source();s['messages'].append(reply('90000.000001'))
    r=extract_announcement(s)
    assert r.author['recorded_role']=='TEAM_LEAD'
    assert r.replies[0]['author']['recorded_role']=='ENGINEER'
    assert r.replies[0]['original_message']==s['messages'][1]
    assert r.reactions==s['messages'][0]['reactions']
    assert r.authority['approval_status']=='UNKNOWN'
    assert r.authority['reactions_are_not_approval']
    assert r.record_kind=='announcement' and r.effective_at is None and not r.supersedes
    s['users'].pop('u1')
    assert extract_announcement(s).author['recorded_role'] is None


def test_structured_decision_effective_date_and_explicit_approval_only():
    s=source();s['messages'][0].update(record_kind='decision',approval={'by':'u1','marker':'synthetic'},
        effective_at='1970-01-04',supersedes=['synthetic-reference'])
    r=extract_announcement(s)
    assert r.document_type=='decision' and r.effective_at=='1970-01-04'
    assert r.supersedes==['synthetic-reference']
    assert r.authority['approval_status']=='EXPLICIT_SOURCE_MARKER'
    with pytest.raises(ValueError,match='mirroring'):extract_announcement(source('GENERAL'))


def test_reruns_are_idempotent_and_edits_have_stable_document_identity(tmp_path):
    s=source();a=extract_announcement(s,captured_at='1970-01-03T00:00:00Z')
    first=store_source(a,tmp_path);saved=Path(first['path']).read_bytes()
    s['extraction_window']={'start':'1970-01-02T00:00:00Z','cutoff':'1970-01-03T00:00:00Z'}
    again=extract_announcement(s,captured_at='1970-01-04T00:00:00Z')
    assert store_source(again,tmp_path)['status']=='DUPLICATE'
    s['messages'][0].update(text='Synthetic revision.',edited={'ts':'90000.000001'})
    b=extract_announcement(s);second=store_source(b,tmp_path)
    assert second['status']=='REVISION' and b.record_id==a.record_id and b.version_id!=a.version_id
    assert second['previous_version_ids']==[a.version_id]
    assert Path(first['path']).read_bytes()==saved
    assert store_source(b,tmp_path)['status']=='DUPLICATE'
    assert len(list(tmp_path.rglob('source.json')))==2


def test_manual_historical_file_is_protected_and_deduplicates_extraction(tmp_path):
    r=extract_announcement(source());manual=write(tmp_path/'synthetic/manual/source-v1.json',r)
    before=manual.read_bytes()
    assert store_source(r,tmp_path)['status']=='DUPLICATE'
    assert not (tmp_path/'synthetic/extracted').exists()
    s=source();s['messages'][0]['text']='Synthetic changed content.'
    assert store_source(extract_announcement(s),tmp_path)['status']=='REVISION'
    assert manual.read_bytes()==before


def test_project_isolation_missing_scope_and_explicit_shared_scope(tmp_path):
    first=store_source(extract_announcement(source()),tmp_path)
    s=source();s['project_id']='other'
    assert store_source(extract_announcement(s),tmp_path)['status']=='NEW'
    assert Path(first['path']).is_file()
    s['project_id']=None;r=extract_announcement(s)
    assert r.scope=='unknown' and '_unknown' in Path(store_source(r,tmp_path)['path']).parts
    s['messages'][0]['scope']='shared';r=extract_announcement(s)
    assert r.scope=='shared' and 'cross_project' in Path(store_source(r,tmp_path)['path']).parts
    s=source();s['project_id']='cross_project'
    with pytest.raises(ValueError,match='explicit shared'):extract_announcement(s)


def test_broken_manual_source_and_atomic_write_failure_are_not_silently_overwritten(tmp_path,monkeypatch):
    manual=write(tmp_path/'synthetic/manual/invalid.json',{'not':'source content'})
    before=manual.read_bytes()
    with pytest.raises(ValueError):store_source(extract_announcement(source()),tmp_path)
    assert manual.read_bytes()==before
    from threadsense.agents import topic_pipeline
    def fail(*args,**kwargs):raise PermissionError('Synthetic locked destination')
    monkeypatch.setattr(topic_pipeline,'write_bytes',fail)
    with pytest.raises(PermissionError):store_source(extract_announcement(source()),tmp_path/'fresh')
    assert not list((tmp_path/'fresh').rglob('source.json'))


@pytest.mark.parametrize('kind',['guideline','faq','announcement','decision'])
def test_manual_historical_and_extracted_use_same_ingestion_envelope(tmp_path,kind):
    r=SourceRecord(source={'system':'manual','project_id':'synthetic','manual_key':'synthetic-historical'},
        scope='project',document_type=kind,record_kind=kind,original_text='Synthetic historical source.',
        created_at='2000-01-01T00:00:00Z',authority={'approval_status':'UNKNOWN'})
    a=write(tmp_path/'manual.json',r);b=write(tmp_path/'same-source.json',r)
    extracted=extract_announcement(source());c=write(tmp_path/'extracted.json',extracted)
    docs=list(iter_documents([a,b,c]))
    assert len(docs)==2
    for d in docs:
        assert set(d)=={'document_id','version_id','text','metadata'}
        assert d['metadata']['document_contract']=='knowledge-document-v1'
        assert d['metadata']['citation_provenance']==d['metadata']['source']
        assert d['metadata']['content_sha256'] not in d['text']
        assert 'extraction_window' not in d['text'] and 'inherited_agent1' not in d['text']
    assert normalize_document(r)==normalize_document(r.model_dump())


def test_reply_context_and_inherited_flags_remain_citation_metadata():
    s=source();s['messages'].append(reply('90000.000001'))
    inherited={'review_required':True,'source_sha256':'synthetic-source-hash','candidate_sha256':'synthetic-candidate-hash',
        'lineage':{'source_file':'synthetic-source'},'review_reasons':['Synthetic dispute']}
    r=extract_announcement(s,canonical_member=inherited);d=normalize_document(r)
    assert d['metadata']['inherited_agent1']==inherited
    assert 'by u2 (ENGINEER)' in d['text'] and 'Context reply [90000.000001]' in d['text']
    assert 'Synthetic dispute' not in d['text']
    assert d['metadata']['context_is_not_approved_decision']


@pytest.mark.parametrize('field',['record_id','version_id','content_sha256'])
def test_forged_identity_or_revision_hash_is_rejected(field):
    data=extract_announcement(source()).model_dump();data[field]='wrong'
    with pytest.raises(ValueError,match=field):SourceRecord.model_validate(data)
