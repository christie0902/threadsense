"""Validate the ThreadSense 200-thread *pre-authored* Slack dataset.

Run from repository root:
    python scripts/validate_threadsense_dataset.py

Requires data/evaluation/thread_blueprint_200.json on YOUR machine.
This tool NEVER generates, modifies, or deletes Slack fixture messages.
Ground truth is used only during validation; NEVER expose it to agents.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/fixtures/slack_generated'
BP = ROOT / 'data/evaluation/thread_blueprint_200.json'
CAT = ROOT / 'data/evaluation/topic_catalog.json'
REPORT = ROOT / 'data/evaluation/manual_review_200.csv'
SNAP_START = int(datetime(2026, 10, 1, 12, tzinfo=timezone.utc).timestamp())
SNAP_END = int(datetime(2026, 10, 2, 12, tzinfo=timezone.utc).timestamp())
PROJECT_TL = {'response_preference':'U001','safety_classification':'U006',
              'audio_multimodal':'U006','multilingual_eval':'U001'}
APPROVALS = {'this','agree','white_check_mark'}
NON_APPROVALS = {'eyes','thumbsup','thinking_face','warning','raised_hands'}
HIDDEN_KEYS = {'latent_topic','resolution_state','severity','expected_action','temporal_case',
               'expected_evidence_sources','language_style','ambiguity_level','should_surface',
               'phrasing_variant_group','primary_issue_class','secondary_issue_classes'}


def load(path):
    if not path.is_file():
        raise FileNotFoundError(f'Missing {path}; check extraction paths and your original blueprint.')
    return json.loads(path.read_text(encoding='utf-8'))


def require(ok, message):
    if not ok: raise AssertionError(message)


def user_index(raw):
    if isinstance(raw,list): rows=raw
    elif isinstance(raw.get('users'),list): rows=raw['users']
    else:
        raw=raw.get('users',raw)
        rows=[dict(info,id=uid) for uid,info in raw.items()]
    return {p['id']:p for p in rows}


def main():
    truth=load(BP)
    cat=load(CAT)
    people=user_index(load(DATA/'users.json'))
    paths=sorted((DATA/'channels').glob('C_*.json'))
    require(len(truth)==200 and len({r['thread_id'] for r in truth})==200,
            'Your blueprint must contain exactly 200 distinct thread IDs')
    require(len(paths)==12,f'Expected 12 channel files, found {len(paths)}')
    expected={r['thread_id']:r for r in truth}
    observed={}
    project_counts=Counter(); group_counts=Counter(); states=Counter()
    reaction_counts=Counter(); roots=Counter(); reply_texts=Counter()
    reply_total=0; endorsements=0; resolved_emoji_only=0
    historic=0; manual=[]; contradictions=[]; all_ts=set()
    for path in paths:
        channel=load(path)
        meta=channel['channel']
        require(meta['id']==path.stem,f'Channel ID mismatch {path}')
        require(meta['channel_type'] in ('GENERAL','QA','ANNOUNCEMENTS'),f'Bad channel {path}')
        require(set(channel)=={'channel','history','replies'},f'Unexpected top-level keys {path}')
        require(set(channel['replies']) <= {str(x['ts']) for x in channel['history']},f'Orphan replies {path}')
        for first in channel['history']:
            tid=str(first['ts'])
            require(tid in expected and tid not in observed,f'Missing/extra/duplicate thread {tid}')
            record=expected[tid]
            require((record['project_id'],record['batch_id'],record['channel_type'],record['channel_id'])==
                    (meta['project_id'],meta['batch_id'],meta['channel_type'],meta['id']),
                    f'Blueprint location mismatch {tid}; do NOT edit labels to make it pass')
            require(first.get('language')==record.get('language'),f'Language mismatch {tid}')
            require(SNAP_START <= int(tid.split('.')[0]) < SNAP_END,f'Root out of window {tid}')
            require(first['user'] in people,f'Unknown author {tid}')
            require(first['source'] in {'USER','WORKFLOW','BOT'},f'Invalid source {tid}')
            require(first['text'].strip(),f'Blank root {tid}')
            if meta['channel_type']=='ANNOUNCEMENTS':
                require(people[first['user']]['role']=='TEAM_LEAD',f'Non-TL announcement {tid}')
            msgs=channel['replies'].get(tid,[])
            # Empty replies entry means a standalone message; otherwise first item duplicates root.
            if msgs:
                require(msgs[0]==first,f'Root snapshots differ {tid}')
            else: msgs=[first]
            require(len(msgs)-1==first.get('reply_count',0),f'Reply count mismatch {tid}')
            require(all(str(m.get('thread_ts'))==tid for m in msgs[1:]),f'Bad thread pointers {tid}')
            tvals=[(int(m['ts'].split('.')[0]),int(m['ts'].split('.')[1])) for m in msgs]
            require(tvals==sorted(tvals) and len(tvals)==len(set(tvals)),f'Non-monotonic replies {tid}')
            require(all(SNAP_START <= x[0] < SNAP_END for x in tvals),f'Reply outside window {tid}')
            require(all(m['ts'] not in all_ts for m in msgs),f'Global timestamp collision in {tid}')
            all_ts.update(m['ts'] for m in msgs)
            tl=PROJECT_TL[record['project_id']]
            require(people.get(tl,{}).get('role')=='TEAM_LEAD',f'TL role is wrong for {tid}')
            tl_authored_reply=any(m['user']==tl for m in msgs[1:])
            tl_approvals=[]
            for i,m in enumerate(msgs):
                require(m['user'] in people,f'Unknown message author in {tid}')
                require(isinstance(m['text'],str) and m['text'].strip(),f'Empty message in {tid}')
                require(m.get('source') in {'USER','WORKFLOW','BOT'},f'Bad source in {tid}')
                require(not (HIDDEN_KEYS & set(m)),f'Hidden evaluation metadata on message {tid}')
                require(isinstance(m.get('reactions'),list),f'Missing reactions list {tid}')
                for r in m['reactions']:
                    require(isinstance(r,dict) and r.get('name'),f'Invalid reaction record {tid}: {r!r}')
                    users=r.get('users'); count=r.get('count')
                    require(isinstance(users,list) and count==len(users) and len(set(users))==len(users),
                            f'Reaction attribution/count inconsistent in {tid}: {r!r}')
                    require(all(u in people and u!=m['user'] for u in users),f'Unknown/self reactor in {tid}: {r!r}')
                    reaction_counts[r['name']]+=1
                    if r['name'] in APPROVALS and tl in users:
                        require(i>0, f'TL approval on initial question in {tid}')
                        require(m['user'] != tl, f'TL approval on own reply in {tid}')
                        require(people[m['user']]['role'] in {'TUTOR','QA_TUTOR'},
                                f'TL approval on non-trainer reply in {tid}')
                        require(not m['text'].rstrip().endswith('?'),f'TL approves question instead of answer: {tid}')
                        tl_approvals.append((i,r['name']))
            require(not any(msgs[i]['text']==msgs[j]['text'] for i in range(1,len(msgs)) for j in range(i+1,len(msgs))),
                    f'Duplicate replies in thread {tid}')
            state=record['resolution_state']
            if record.get('primary_issue_class') is not None:
                if state=='UNRESOLVED':
                    require(not tl_authored_reply and not tl_approvals,
                            f'Unresolved thread contains TL response/approval {tid}')
                elif state=='PARTIALLY_RESOLVED':
                    require(tl_authored_reply and not tl_approvals,
                            f'Partial thread should have a pending TL message, no approval: {tid}')
                elif state=='RESOLVED_IN_THREAD':
                    require(tl_authored_reply or tl_approvals,
                            f'Resolved thread has no TL answer or attributed endorsement {tid}')
                else: require(False,f'Invalid resolution state for {tid}')
            if state=='RESOLVED_IN_THREAD' and tl_approvals and not tl_authored_reply:
                resolved_emoji_only+=1
            endorsements+=len(tl_approvals)
            reply_total += len(msgs)-1
            project_counts[meta['project_id']]+=1
            group_counts[(record['project_id'],record['latent_topic'])]+=1
            states[state]+=1
            roots[first['text']]+=1
            reply_texts.update(m['text'] for m in msgs[1:])
            if record.get('temporal_case','NONE')!='NONE': historic+=1
            # A simple semantic smoke check; NOT a substitute for human review.
            root_lower=first['text'].lower()
            for m in msgs[1:]:
                text=m['text'].lower()
                if record['latent_topic']=='non_latin_script_rendering':
                    if ('hangul' in root_lower or 'korean' in root_lower) and ('japanese glyphs' in text):
                        contradictions.append(f'{tid}: Korean issue described as Japanese glyphs')
                    if ('japanese' in root_lower or 'kanji' in root_lower) and ('hangul characters' in text):
                        contradictions.append(f'{tid}: Japanese issue described as Hangul')
                if record['latent_topic']=='major_error_definition' and 'changes the final recommendation' in root_lower:
                    if 'recommendation would not change' in text:
                        contradictions.append(f'{tid}: final recommendation contradiction')
                if record['latent_topic']=='code_switching_evaluation' and 'user code-switched' in root_lower:
                    if 'specified monolingual prompt' in text:
                        contradictions.append(f'{tid}: false monolingual assumption')
            manual.append({'thread_id':tid,'project':record['project_id'],'channel':meta['id'],
                           'topic_HIDDEN':record['latent_topic'],'state_HIDDEN':state,
                           'temporal_HIDDEN':record.get('temporal_case','NONE'),
                           'root':first['text'],'replies':' || '.join(f"{m['user']}: {m['text']}" for m in msgs[1:]),
                           'tl_approval_emojis':','.join(s for i,s in tl_approvals),
                           'requires_historical_evidence':record.get('temporal_case','NONE')!='NONE'})
            observed[tid]=True
    require(set(observed)==set(expected), f'Blueprint mismatch: missing={set(expected)-set(observed)}')
    require(dict(project_counts)=={'response_preference':55,'safety_classification':50,
             'audio_multimodal':45,'multilingual_eval':50},f'Project counts wrong: {project_counts}')
    for scenario in cat['topics']:
        p=scenario['project_id']
        if scenario['topic_kind']=='ISSUE':
            actual=group_counts[(p,scenario['latent_topic'])]
            require(actual==scenario['thread_target'],f'Scenario count mismatch: {p}/{scenario["latent_topic"]}, got {actual}')
        else:
            for item in scenario['individual_latent_topics']:
                require(group_counts[(p,item['latent_topic'])]==1, f'Routine topic not singleton: {item["latent_topic"]}')
    require(dict(states)=={'UNRESOLVED':90,'PARTIALLY_RESOLVED':55,'RESOLVED_IN_THREAD':55},
            f'Resolution mix mismatch: {states}')
    require(not contradictions,f'Contextual contradictions detected: {contradictions}')
    require(endorsements>=12 and resolved_emoji_only>=12,f'Insufficient TL reaction-only cases: {endorsements}, {resolved_emoji_only}')
    require(reaction_counts['this']>0 and reaction_counts['agree']>0,
            f'Missing requested TL :this: / :agree: reactions: {reaction_counts}')
    duplicate_ratio=sum(v-1 for v in reply_texts.values())/max(1,reply_total)
    require(duplicate_ratio < 0.15,f'Excess repeated reply text: {duplicate_ratio:.1%}')
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    with REPORT.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(manual[0]));writer.writeheader();writer.writerows(sorted(manual,key=lambda x:x['thread_id']))
    print('PASS: structural, ID, project, topic, resolution, reaction and duplicate-text checks')
    print('Threads:',len(observed),'Channels:',len(paths),'Replies:',reply_total)
    print('Projects:',dict(project_counts),'Resolution:',dict(states))
    print('TL reaction approvals:',endorsements,'Reaction-only resolved threads:',resolved_emoji_only)
    print('Emoji counts:',dict(reaction_counts))
    print('Duplicate reply ratio:',f'{duplicate_ratio:.1%}','Historical cases pending sources:',historic)
    print('Human review queue:',REPORT)
    print('LIMITATION: semantic realism/policy accuracy require human review and source reconciliation.')

if __name__=='__main__': main()
