"""Offline assembly preserves original attempts, failure evidence and reviews."""
import json
import runpy

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.handoff_inputs import ROOT,read_json,file_hash,digest
from threadsense.agents import topic_pipeline as pipeline, verification_requests as transport
from threadsense.agents.topic_effective import load_effective_output
from tests.agent2_inventory_fixtures import GIDS,payload
from tests.agent2_structured_fixtures import reviewed_draft

assemble=runpy.run_path(str(ROOT/'scripts/assemble_agent2_dataset.py'))['assemble_dataset']


@pytest.fixture
def runs(tmp_path,monkeypatch):
    monkeypatch.setenv('THREADSENSE_MODEL','openai/gpt-5.4-2026-03-05')
    monkeypatch.setenv('THREADSENSE_AGENT2_REASONING_EFFORT','low')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-offline-key')
    def send(endpoint,body,key):
        gid=json.loads(json.loads(body)['messages'][1]['content'])['candidate_group_id']
        return 200,json.dumps({'model':'gpt-5.4-2026-03-05','choices':[{'finish_reason':'stop',
            'message':{'content':json.dumps(reviewed_draft(gid))}}]}).encode(),None
    monkeypatch.setattr(transport,'send_once',send)
    selected=[payload(GIDS[0]),payload(GIDS[1])]
    paths=[tmp_path/'prior',tmp_path/'new']
    for p,path in zip(selected,paths): pipeline.execute_batch([p],path,run=True,maximum_requests=1)
    def forbidden(*args,**kwargs): raise AssertionError('Assembly must never call a model.')
    monkeypatch.setattr(transport,'send_once',forbidden)
    registry=tmp_path/'registry.json'; pipeline.write_json(registry,{'version':1,'supplements':[]})
    return selected,paths,registry


def test_exact_reuse_keeps_prior_reviews_sources_and_attempt_accounting(runs,tmp_path):
    selected,paths,registry=runs
    d=paths[1]/'records'/GIDS[1]
    binding={k:file_hash(d/name) for k,name in [('input_file_sha256','input.json'),('raw_draft_sha256','analysis.raw.txt'),('export_result_sha256','result.json')]}
    review=tmp_path/'synthetic_review.json'
    pipeline.write_json(review,{'run':str(paths[1]),'origin':'Synthetic offline review',
        'entries':[{'candidate_group_id':GIDS[1],'binding':binding,'assisted_content_review_required':True,
        'findings':[{'category':'synthetic_scope_dispute','source_evidence':[{'quote':'Synthetic test-only evidence.'}]}]}]})
    pipeline.write_json(registry,{'version':1,'supplements':[{'run':str(paths[1]),'path':str(review),'sha256':file_hash(review)}]})
    original=load_effective_output(paths[1],registry=registry)
    hashes={str(p):file_hash(p) for path in paths for p in path.rglob('*') if p.is_file()}
    out=tmp_path/'final'
    m=assemble([(paths[0],'reused'),(paths[1],'new')],out,selected,registry=registry)
    assert m['new_request_attempts']==m['reused_original_attempts']==1 and m['total_original_attempts']==2
    assert m['groups']==2 and m['identities']==8 and m['inherited_review_obligations']==2
    assert m['processing_counts']=={'CONSOLIDATED':2} and m['assembly_model_calls']==0
    view=load_effective_output(out,registry=registry)
    assert {o['obligation_id'] for o in view['applied_content_obligations']}=={o['obligation_id'] for o in original['applied_content_obligations']}
    assert view['review_binding_status']=='VALID'
    assert all(file_hash(p)==h for p,h in hashes.items())
    for path in paths:
        row=read_json(path/'consolidations.json')[0]
        assert read_json(out/'records'/row['candidate_group_id']/'result.json')==row
    with pytest.raises(FileExistsError): assemble([(paths[0],'reused'),(paths[1],'new')],out,selected,registry=registry)


@pytest.mark.parametrize('mutation',['duplicate','missing','model','binding'])
def test_incompatible_or_incomplete_collection_fails_before_publication(runs,tmp_path,mutation):
    selected,paths,registry=runs
    sources=[(paths[0],'reused'),(paths[1],'new')]
    if mutation=='duplicate': sources[1]=(paths[0],'new')
    if mutation=='missing': sources.pop()
    if mutation=='model':
        m=read_json(paths[1]/'manifest.json'); m['config']['model']='openai/other'
        m['config_sha256']=digest(m['config']); pipeline.write_json(paths[1]/'manifest.json',m)
    if mutation=='binding':
        d=paths[1]/'records'/GIDS[1]; p=read_json(d/'input.json'); p['members'][0]['agent1_record']['candidate_sha256']='changed'
        pipeline.write_json(d/'input.json',p)
    before=file_hash(registry)
    with pytest.raises(ValueError): assemble(sources,tmp_path/'final',selected,registry=registry)
    assert file_hash(registry)==before and not (tmp_path/'final').exists()


def test_unknown_completion_and_failure_are_preserved_without_retry(runs,tmp_path):
    selected,paths,registry=runs
    d=paths[1]/'records'/GIDS[1]
    # Synthetic interrupted transport, retaining explicit request and diagnostics.
    from threadsense.agents.topic_consolidation_v6 import export_result
    row=export_result(selected[1],state='INTERRUPTED',error='Synthetic unknown completion; do not retry.')
    pipeline.write_json(d/'result.json',row)
    pipeline.write_json(paths[1]/'consolidations.json',[row])
    status=read_json(d/'completion_status.json'); status['provider_completion_unknown']=True
    pipeline.write_json(d/'completion_status.json',status)
    m=assemble([(paths[0],'reused'),(paths[1],'new')],tmp_path/'final',selected,registry=registry)
    assert m['processing_counts']=={'CONSOLIDATED':1,'INTERRUPTED':1}
    assert m['unknown_completion_requests']==[GIDS[1]] and m['new_request_attempts']==1
    view=load_effective_output(tmp_path/'final',registry=registry)
    failed=next(r for r in view['records'] if r['candidate_group_id']==GIDS[1])
    assert failed['research_handoff']['members']==selected[1]['members']
    assert len(failed['inherited_review_obligations'])==2 and failed['review_required']
