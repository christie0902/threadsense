"""Versioned source files and a provider-neutral ingestion envelope, without search.

Daily selection lives in routing.py. Historical/manual ingestion has no time limit.
No embedding, vector provider, semantic extraction, or authority inference here.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from threadsense.routing import aware, digest, slack_datetime, route_kind


class SourceIdentity(BaseModel):
    model_config = ConfigDict(extra='forbid')
    system: Literal['slack','manual']
    workspace_id: str | None = None
    project_id: str | None = None
    batch_id: str | None = None
    channel_id: str | None = None
    thread_id: str | None = None
    message_id: str | None = None
    manual_key: str | None = None
    reference: str | None = None
    permalink: str | None = None

    @model_validator(mode='after')
    def identity_complete(self):
        if self.system=='slack' and not all((self.channel_id,self.thread_id,self.message_id)):
            raise ValueError('Slack document identity needs channel/thread/message IDs.')
        if self.system=='manual' and not self.manual_key:
            raise ValueError('Manual source needs a stable manual_key.')
        return self


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['knowledge-source-v1'] = 'knowledge-source-v1'
    record_id: str = ''
    version_id: str = ''
    content_sha256: str = ''
    source: SourceIdentity
    scope: Literal['project','shared','unknown']
    document_type: Literal['announcement','decision','guideline','faq']
    record_kind: Literal['announcement','status_update','decision','guideline','faq']
    original_text: str
    author: dict[str,Any] = Field(default_factory=dict)
    replies: list[dict[str,Any]] = Field(default_factory=list)
    reactions: list[Any] = Field(default_factory=list)
    source_metadata: dict[str,Any] = Field(default_factory=dict)
    authority: dict[str,Any] = Field(default_factory=dict)
    created_at: str | None = None
    edited_at: str | None = None
    source_capture_at: str | None = None
    captured_at: str | None = None
    extraction_window: dict[str,str] | None = None
    effective_at: str | None = None
    supersedes: list[str] = Field(default_factory=list)
    inherited_agent1: dict[str,Any] | None = None
    previous_version_ids: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_source(self):
        if self.scope=='project' and not self.source.project_id:
            raise ValueError('Project scope requires an explicit project.')
        if self.scope=='unknown' and self.source.project_id is not None:
            raise ValueError('Known project cannot use unknown scope.')
        if self.source.project_id=='cross_project' and self.scope!='shared':
            raise ValueError('cross_project requires explicit shared scope.')
        if self.document_type != ('announcement' if self.record_kind=='status_update' else self.record_kind):
            raise ValueError('Document type and structured record kind disagree.')
        for field in ('created_at','edited_at','source_capture_at','captured_at'):
            if getattr(self,field) is not None:
                aware(getattr(self,field))
        if self.effective_at is not None:
            if len(self.effective_at)==10:date.fromisoformat(self.effective_at)
            else:aware(self.effective_at)
        if self.extraction_window is not None:
            a,b=aware(self.extraction_window['start']),aware(self.extraction_window['cutoff'])
            if b<=a:raise ValueError('Invalid extraction window.')
        identity=self.source.model_dump(exclude={'reference','permalink'})
        rid='knowledge_'+digest(identity)
        # Observation times/window and previous observations are receipts, not content.
        content=self.model_dump(exclude={'record_id','version_id','content_sha256',
            'captured_at','source_capture_at','extraction_window','previous_version_ids'})
        sha=digest(content);vid='version_'+sha
        for field,expected in (('record_id',rid),('version_id',vid),('content_sha256',sha)):
            if getattr(self,field) not in ('',expected):
                raise ValueError(f'{field} does not match source identity/content.')
            setattr(self,field,expected)
        if self.version_id in self.previous_version_ids:
            raise ValueError('Revision cannot refer to itself.')
        return self


def _attributed(raw, users):
    user=users.get(raw.get('user')) or {}
    return {'message_id':raw['ts'],'original_text':raw.get('text',''),
        'author':{'id':raw.get('user'),'name':user.get('name'),'recorded_role':user.get('role')},
        'created_at':slack_datetime(raw['ts']).isoformat(),
        'edited_at':slack_datetime(raw['edited']['ts']).isoformat() if raw.get('edited',{}).get('ts') else None,
        'permalink':raw.get('permalink'),'reactions':deepcopy(raw.get('reactions',[])),
        'original_message':deepcopy(raw)}


def extract_announcement(thread, *, captured_at=None, canonical_member=None):
    if route_kind(thread)!='ANNOUNCEMENT':
        raise ValueError('Discussion mirroring is not enabled; a TL reply alone is not a decision marker.')
    roots=[m for m in thread['messages'] if m['ts']==thread['thread_id']]
    if len(roots)!=1:raise ValueError('Exactly one original parent is required.')
    raw=roots[0];root=_attributed(raw,thread['users'])
    kind=raw.get('record_kind','announcement')
    if kind not in {'announcement','status_update','decision'}:
        raise ValueError('Unsupported explicit announcement source classification.')
    explicit_scope=raw.get('scope',thread.get('channel_metadata',{}).get('scope'))
    scope='shared' if explicit_scope=='shared' else 'project' if thread.get('project_id') else 'unknown'
    return SourceRecord(source=SourceIdentity(system='slack',
        **{k:thread.get(k) for k in ('workspace_id','project_id','batch_id','channel_id','thread_id')},
        message_id=raw['ts'],reference=raw.get('source_reference'),permalink=raw.get('permalink')),
        scope=scope,document_type='decision' if kind=='decision' else 'announcement',record_kind=kind,
        original_text=root['original_text'],author=root['author'],reactions=root['reactions'],
        replies=[_attributed(m,thread['users']) for m in thread['messages'] if m['ts']!=raw['ts']],
        source_metadata={'root_message':deepcopy(raw),'channel':deepcopy(thread.get('channel_metadata',{}))},
        authority={'author_recorded_role':root['author']['recorded_role'],
            'approval_status':'EXPLICIT_SOURCE_MARKER' if raw.get('approval') is not None else 'UNKNOWN',
            'explicit_approval':deepcopy(raw.get('approval')),
            'channel_membership_is_not_approval':True,'reactions_are_not_approval':True},
        created_at=root['created_at'],edited_at=root['edited_at'],source_capture_at=thread.get('source_capture_at'),
        captured_at=aware(captured_at or datetime.now(timezone.utc)).isoformat(),
        extraction_window=thread.get('extraction_window'),effective_at=raw.get('effective_at'),
        supersedes=deepcopy(raw.get('supersedes',[])),inherited_agent1=deepcopy(canonical_member))


def normalize_document(value):
    """Same source/version -> same IDs for later shared-index upsert. No date filter."""
    r=SourceRecord.model_validate(value.model_dump() if isinstance(value,SourceRecord) else value)
    text=r.original_text
    for reply in r.replies:
        author=reply.get('author',{})
        text+=f"\n\nContext reply [{reply.get('message_id')}] by {author.get('id')} ({author.get('recorded_role')}):\n{reply.get('original_text','')}"
    metadata=r.model_dump(exclude={'original_text'})
    metadata.update({'document_type':r.document_type,'project_id':r.source.project_id,
        'batch_id':r.source.batch_id,'document_contract':'knowledge-document-v1',
        'citation_provenance':r.source.model_dump(),
        'context_is_not_approved_decision':True})
    return {'document_id':r.record_id,'version_id':r.version_id,'text':text,'metadata':metadata}


def iter_documents(paths):
    """Normalize manual historical and extracted sources; reject inconsistent duplicates.

    JSON files hold one record or a list. Markdown files (mock-knowledge-markdown-v1)
    hold one record each; one authoring document_id/version may not have two contents.
    """
    seen={};authored={}
    for path in sorted(map(Path,paths)):
        if path.suffix.lower()=='.md':
            from threadsense.knowledge_markdown import markdown_source
            records=[markdown_source(path)]
        else:
            value=json.loads(path.read_text(encoding='utf-8-sig'))
            records=value if isinstance(value,list) else [value]
        for raw in records:
            document=normalize_document(raw);key=(document['document_id'],document['version_id'])
            authoring=document['metadata']['source_metadata'].get('authoring')
            if authoring:
                claim=(authoring['document_id'],authoring['version'])
                if authored.setdefault(claim,key)!=key:
                    raise ValueError(f'Conflicting contents claim authoring identity {claim[0]}@{claim[1]}.')
            if key in seen:
                if seen[key]['metadata']['content_sha256']!=document['metadata']['content_sha256'] or seen[key]['text']!=document['text']:
                    raise ValueError('Conflicting source/version duplicate.')
                continue
            seen[key]=document
            yield document


def store_source(record, directory):
    """Thin immutable source-file persistence; never replace a prior or manual file.

    Use the existing no-retry atomic writer in a fresh version directory. Publish
    only completed *.json; a failed write is visible in the extraction manifest.
    One extraction writer per directory. No indexes or retrieval API are created.
    """
    from threadsense.agents.topic_pipeline import write_bytes
    r=SourceRecord.model_validate(record.model_dump() if isinstance(record,SourceRecord) else record)
    root=Path(directory).resolve()
    project='cross_project' if r.scope=='shared' else r.source.project_id or '_unknown'
    if not all(c.isalnum() or c in '_-' for c in project):
        raise ValueError('Unsafe project path.')
    folder=root/project/'extracted'/r.record_id
    prior=[]
    # Manual sources can coexist anywhere under this knowledge source root.
    # Inspect records, never modify them. Malformed sources fail explicitly.
    project_root=root/project
    for path in sorted(project_root.rglob('*.json')) if project_root.exists() else []:
        value=json.loads(path.read_text(encoding='utf-8-sig'))
        for raw in value if isinstance(value,list) else [value]:
            old=SourceRecord.model_validate(raw)
            if old.record_id!=r.record_id:continue
            if old.version_id==r.version_id:
                return {'status':'DUPLICATE','document_id':r.record_id,'version_id':r.version_id,'path':str(path)}
            prior.append(old.version_id)
    r.previous_version_ids=sorted(set(prior+r.previous_version_ids))
    destination=folder/r.version_id/'source.json'
    destination.parent.mkdir(parents=True,exist_ok=False)
    body=(json.dumps(r.model_dump(),ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
    write_bytes(destination,body)
    return {'status':'REVISION' if prior else 'NEW','document_id':r.record_id,
            'version_id':r.version_id,'path':str(destination),'previous_version_ids':r.previous_version_ids}
