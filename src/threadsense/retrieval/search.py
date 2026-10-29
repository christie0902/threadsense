"""Read-only hybrid retrieval: filter -> dense + BM25 -> RRF -> dedupe -> MMR.

Scope, batch, date, type, status and tag filters select the eligible chunk set
first; both the dense and BM25 paths then rank only those chunks. Dense ranking
is exact cosine over the embeddings persisted in Chroma, not Chroma's HNSW
query: the corpus is small, exact search has no approximation error, and the
ChromaDB 1.5.9 HNSW segment reader intermittently failed ("Nothing found on
disk") when several collections were read. Returned text is source evidence,
never instructions. Scores order evidence; they are not AdviceCard confidence.
"""
from hashlib import sha256
import json
import math
from pathlib import Path

from threadsense.retrieval.bm25 import BM25
from threadsense.retrieval.config import (
    CHUNKING_VERSION, COLLECTION_NAMES, DEFAULTS, DENSE_SEARCH, EMBEDDING, HNSW, INDEX_DIR,
)
from threadsense.retrieval.index import INDEX_FORMAT, RetrievalIndexError, chroma_client
from threadsense.retrieval.versions import CURRENT_STATES, VersionIndex, lineage_of
from threadsense.routing import aware

MODES = ('hybrid', 'dense', 'bm25')


def _time(value):
    if value is None:
        return None
    return aware(value + 'T00:00:00Z' if len(value) == 10 else value)


# Fields that must match before identical text may share one displayed result.
DEDUPE_FIELDS = ('project_id', 'batch_id', 'scope', 'source_date', 'effective_at', 'valid_until', 'authority_role',
                 'authority_actor', 'approval_status', 'status', 'decision_status', 'execution_status',
                 'outcome_status', 'record_kind', 'authoring_record_kind', 'event_series_id', 'review_required')


def dedupe_key(chunk):
    m = chunk['metadata']
    return (' '.join(chunk['text'].split()), *(json.dumps(m.get(f), sort_keys=True) for f in DEDUPE_FIELDS))


def rrf(rankings, k):
    """Reciprocal Rank Fusion: sum of 1 / (k + rank) over the paths that ranked the chunk."""
    fused = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, 1):
            fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)
    return fused


def mmr(candidates, relevance, vectors, *, top_k, lam):
    """Maximal Marginal Relevance. relevance in [0, 1]; redundancy = max cosine to selected, clipped to [0, 1]."""
    selected, scores, remaining = [], {}, list(candidates)
    while remaining and len(selected) < top_k:
        def value(key):
            redundancy = max((max(0.0, sum(a * b for a, b in zip(vectors[key], vectors[s]))) for s in selected), default=0.0)
            return lam * relevance[key] - (1 - lam) * redundancy
        best = min(remaining, key=lambda key: (-round(value(key), 12), candidates.index(key)))
        scores[best] = value(best)
        selected.append(best)
        remaining.remove(best)
    return selected, scores


class Retriever:
    def __init__(self, index_dir=INDEX_DIR, *, encoder=None):
        self.index_dir = Path(index_dir)
        path = self.index_dir/'manifest.json'
        if not path.is_file():
            raise RetrievalIndexError(f'No complete index at {self.index_dir}; run scripts/build_retrieval_index.py.')
        self.manifest = json.loads(path.read_text(encoding='utf-8'))
        expected = {'index_format': INDEX_FORMAT, 'chunking_version': CHUNKING_VERSION, 'hnsw': HNSW,
                    'dense_search': DENSE_SEARCH}
        if any(self.manifest.get(k) != v for k, v in expected.items()) or any(
                self.manifest['embedding'].get(k) != v for k, v in EMBEDDING.items()):
            raise RetrievalIndexError('Index was built with a different format, chunking or embedding configuration; rebuild.')
        for name in ('chunks', 'documents'):
            body = (self.index_dir/f'{name}.json').read_bytes()
            if sha256(body).hexdigest() != self.manifest[f'{name}_sha256']:
                raise RetrievalIndexError(f'{name}.json differs from the manifest; rebuild.')
        self.chunks = {c['chunk_id']: c for c in json.loads((self.index_dir/'chunks.json').read_text(encoding='utf-8'))}
        self._documents = None
        self.client = chroma_client(self.index_dir/'chroma')
        self.collections = {name: self.client.get_collection(name) for name in COLLECTION_NAMES}
        # Dense search is exact cosine over the embeddings stored in Chroma (see DENSE_SEARCH).
        self.vectors, counts = {}, {}
        for name, collection in self.collections.items():
            got = collection.get(include=['embeddings'])
            counts[name] = len(got['ids'])
            self.vectors.update({k: [float(x) for x in v] for k, v in zip(got['ids'], got['embeddings'])})
        if counts != self.manifest['collection_chunks'] or set(self.vectors) != set(self.chunks):
            raise RetrievalIndexError(f'Chroma contents {counts} differ from the manifest/sidecar; rebuild.')
        if any(len(v) != self.manifest['embedding']['dimension'] for v in self.vectors.values()):
            raise RetrievalIndexError('Stored embedding dimension differs from the manifest; rebuild.')
        self.versions = VersionIndex(self.chunks)
        self.bm25 = BM25({k: c['indexed_text'] for k, c in self.chunks.items()},
                         k1=DEFAULTS['bm25_k1'], b=DEFAULTS['bm25_b'])
        self._encoder = encoder

    @property
    def encoder(self):
        if self._encoder is None:
            from threadsense.retrieval.embeddings import SentenceEncoder
            self._encoder = SentenceEncoder()
            if self._encoder.dimension != self.manifest['embedding']['dimension']:
                raise RetrievalIndexError('Query encoder dimension differs from the index.')
        return self._encoder

    def staleness(self, **sources):
        """Recompute the source fingerprint (no embeddings); never rebuilds."""
        from threadsense.retrieval.index import plan
        _, _, _, core = plan(self.encoder, **sources)
        same = core['corpus_fingerprint'] == self.manifest['corpus_fingerprint'] and \
            core['chunk_fingerprint'] == self.manifest['chunk_fingerprint']
        return 'CURRENT' if same else 'STALE'

    def document(self, document_id, version_id):
        """Full normalized metadata for one source version (citations, review lineage)."""
        if self._documents is None:
            self._documents = json.loads((self.index_dir/'documents.json').read_text(encoding='utf-8'))
        return self._documents[f'{document_id}@{version_id}']

    def eligible(self, project, **filters):
        """Filter-eligible chunks with their scope/date/version annotations (no ranking)."""
        return self.select(project, **filters)['eligible']

    def select(self, project, *, version_mode=DEFAULTS['version_mode'], **filters):
        """Scope/date/metadata filters, then version applicability; both precede ranking."""
        if version_mode not in {'current', 'history'}:
            raise ValueError("version_mode must be 'current' or 'history'.")
        keep = self._filter(project, **filters)
        reference = filters.get('as_of') or self.manifest['cutoff']
        states, diagnostics = self.versions.assess(reference, filters.get('batch'))
        seen, withheld, unverified = set(), [], []
        for key in sorted(keep):
            chunk = self.chunks[key]
            lineage = lineage_of(chunk)
            seen.add(lineage)
            state = states.get(chunk['version_id'])
            applied, unresolved = self.versions.section_supersession(chunk, states)
            unverified += [{'chunk_id': key, **u} for u in unresolved]
            siblings = [self.versions.describe(r, states) for v, r in self.versions.lineages[lineage].items()
                        if v != chunk['version_id']]
            info = {'mode': version_mode, 'lineage': list(lineage), 'state': state,
                    # One label for consumers: a current revision whose section was replaced is not applicable.
                    'applicability': 'SECTION_SUPERSEDED' if applied and state in CURRENT_STATES else state,
                    'reference_time': reference, 'reference_basis': 'as_of' if filters.get('as_of') else 'index_cutoff',
                    'other_revisions': siblings, 'section_superseded_by': applied, 'unverified_supersession': unresolved,
                    'supersedes': chunk['supersession']['document_supersedes']}
            if version_mode == 'current' and (state not in CURRENT_STATES or applied):
                withheld.append({'chunk_id': key, 'citation': chunk['citation'], 'sections': chunk['sections'],
                                 'state': 'SECTION_SUPERSEDED' if state in CURRENT_STATES else state,
                                 'section_superseded_by': applied})
                del keep[key]
                continue
            keep[key]['version'] = info
        relevant = [d for d in diagnostics if tuple(d['lineage']) in seen]
        relevant += [{'kind': 'UNVERIFIED_SUPERSESSION', **u} for u in unverified]
        return {'eligible': keep, 'version_mode': version_mode, 'diagnostics': relevant, 'withheld': withheld}

    def _filter(self, project, *, batch=None, batch_scope=DEFAULTS['batch_scope'], include_shared=False, as_of=None,
                date_from=None, date_to=None, include_undated=True, collections=None, document_types=None,
                statuses=None, record_kinds=None, tags=None, event_series_ids=None):
        if batch_scope not in {'project', 'strict'}:
            raise ValueError("batch_scope must be 'project' or 'strict'.")
        as_of, start, end = _time(as_of), _time(date_from), _time(date_to)
        keep = {}
        for key, chunk in self.chunks.items():
            m = chunk['metadata']
            if not (m['project_id'] == project and m['scope'] == 'project' or include_shared and m['scope'] == 'shared'):
                continue
            relation = None if batch is None else 'same_batch' if m['batch_id'] == batch else \
                'project_wide' if m['batch_id'] is None else 'other_batch'
            if batch_scope == 'strict' and relation == 'other_batch':
                continue
            when = _time(m['source_date'])
            if when is None and not include_undated and (as_of or start or end):
                continue
            if when is not None and (as_of and when > as_of or start and when < start or end and when > end):
                continue
            if collections and chunk['collection'] not in collections:
                continue
            if document_types and m['document_type'] not in document_types and m['authoring_record_kind'] not in document_types:
                continue
            if statuses and not {m['status'], m['decision_status']} & set(statuses):
                continue
            if record_kinds and not {m['record_kind'], m['authoring_record_kind']} & set(record_kinds):
                continue
            if tags and not set(m['tags']) & set(tags):
                continue
            if event_series_ids and m['event_series_id'] not in event_series_ids:
                continue
            keep[key] = {'batch_relation': relation, 'date_status': 'DATED' if when else 'MISSING_SOURCE_DATE',
                         'expired_as_of': bool(as_of and m['valid_until'] and _time(m['valid_until']) < as_of)}
        return keep

    def _dense(self, query, keys, limit):
        """Exact cosine (vectors are normalized) between the query and every eligible chunk."""
        vector = self.encoder.encode([query])[0]
        found = [(sum(a * b for a, b in zip(vector, self.vectors[k])), k) for k in keys]
        found.sort(key=lambda item: (-round(item[0], 9), item[1]))
        return [(k, s) for s, k in found[:limit]], vector

    def search(self, query, project, *, top_k=DEFAULTS['top_k'], candidate_k=DEFAULTS['candidate_k'],
               rrf_k=DEFAULTS['rrf_k'], mmr_lambda=DEFAULTS['mmr_lambda'], mode='hybrid', use_mmr=True, **filters):
        if mode not in MODES:
            raise ValueError(f'mode must be one of {MODES}.')
        selection = self.select(project, **filters)
        eligible = selection['eligible']
        keys = sorted(eligible)
        dense, bm25 = [], []
        if keys and mode in {'hybrid', 'dense'}:
            dense, _ = self._dense(query, keys, candidate_k)
        if keys and mode in {'hybrid', 'bm25'}:
            scored = self.bm25.scores(query, keys)
            bm25 = sorted(scored.items(), key=lambda item: (-round(item[1], 9), item[0]))[:candidate_k]
        dense_rank = {k: i for i, (k, _) in enumerate(dense, 1)}
        bm25_rank = {k: i for i, (k, _) in enumerate(bm25, 1)}
        if mode == 'hybrid':
            fused = rrf([[k for k, _ in dense], [k for k, _ in bm25]], rrf_k)
        else:
            fused = {k: 1.0 / (rrf_k + i) for i, (k, _) in enumerate(dense or bm25, 1)}
        pool = sorted(fused, key=lambda k: (-fused[k], dense_rank.get(k, math.inf), bm25_rank.get(k, math.inf), k))
        # Only identical text with identical scope, date, authority and decision state collapses;
        # the collapsed chunks' provenance stays attached. Complementary records never merge.
        seen, duplicates, unique = {}, {}, []
        for key in pool:
            identity = dedupe_key(self.chunks[key])
            if identity in seen:
                duplicates.setdefault(seen[identity], []).append(key)
                continue
            seen[identity] = key
            unique.append(key)
        if use_mmr and unique:
            # Min-max over the pool puts relevance on [0, 1], the same range as clipped cosine redundancy.
            high, low = max(fused[k] for k in unique), min(fused[k] for k in unique)
            relevance = {k: 1.0 if high == low else (fused[k] - low) / (high - low) for k in unique}
            order, mmr_scores = mmr(unique, relevance, self._vectors(unique), top_k=top_k, lam=mmr_lambda)
        else:
            order, mmr_scores = unique[:top_k], {}
        dense_score, bm25_score = dict(dense), dict(bm25)
        results = []
        for rank, key in enumerate(order, 1):
            chunk = self.chunks[key]
            results.append({
                'rank': rank, 'chunk_id': key, 'collection': chunk['collection'],
                'document_id': chunk['document_id'], 'version_id': chunk['version_id'], 'sections': chunk['sections'],
                'text': chunk['text'], 'citation': chunk['citation'], 'metadata': chunk['metadata'],
                'supersession': chunk['supersession'], **eligible[key],
                'scores': {'dense_rank': dense_rank.get(key), 'dense_cosine': dense_score.get(key),
                           'bm25_rank': bm25_rank.get(key), 'bm25_score': bm25_score.get(key),
                           'rrf_score': fused[key] if mode == 'hybrid' else None, 'mmr_score': mmr_scores.get(key)},
                'duplicate_chunk_ids': duplicates.get(key, []),
                'duplicate_sources': [{'chunk_id': k, 'document_id': self.chunks[k]['document_id'],
                                       'version_id': self.chunks[k]['version_id'], 'citation': self.chunks[k]['citation'],
                                       'metadata': self.chunks[k]['metadata']} for k in duplicates.get(key, [])],
                'evidence_only': True,
            })
        return {'query': query, 'project': project, 'mode': mode, 'use_mmr': use_mmr,
                'filters': {k: v for k, v in filters.items() if v is not None},
                'config': {'top_k': top_k, 'candidate_k': candidate_k, 'rrf_k': rrf_k, 'mmr_lambda': mmr_lambda},
                'eligible_chunks': len(keys), 'dense_candidates': len(dense), 'bm25_candidates': len(bm25),
                'version_mode': selection['version_mode'],
                # Unresolved version/applicability questions go to the Advisor; nothing is chosen here.
                'version_diagnostics': selection['diagnostics'],
                'withheld_by_version': selection['withheld'],
                'results': results,
                'note': 'Ranks are retrieval relevance only; a nonempty result does not show the question is answered.'}

    def _vectors(self, keys):
        return {k: self.vectors[k] for k in keys}
