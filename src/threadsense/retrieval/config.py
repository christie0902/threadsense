"""Versioned retrieval configuration. Changing any value here makes old indexes stale."""
from threadsense.routing import ROOT

INDEX_DIR = ROOT/'.index/retrieval'
KNOWLEDGE_ROOT = ROOT/'data/knowledge'
FIXTURE_ROOT = ROOT/'data/fixtures/slack_generated_demo'
FIXTURE_CUTOFF = '2026-10-02T12:00:00Z'

# Same local model and pinned revision as the approved Agent 2 grouping.
EMBEDDING = {
    'provider': 'sentence-transformers', 'model': 'sentence-transformers/all-MiniLM-L6-v2',
    'revision': 'b9db1e8a0d3a51769172ba8546f282a73f066e47', 'device': 'cpu',
    'normalize_embeddings': True, 'similarity': 'cosine',
    # Symmetric model: queries and documents are encoded identically, with no prefixes.
    'query_prefix': '', 'document_prefix': '',
}
# v2 (2026-10-29): oversized FAQ sections split at question/answer units, and an answer
# continuation repeats its exact question (tracked in each chunk's repeated_context).
CHUNKING_VERSION = 'knowledge-chunks-v2'
COLLECTIONS = {'guideline': 'guidelines', 'faq': 'faq', 'decision': 'decisions', 'announcement': 'decisions'}
COLLECTION_NAMES = ('guidelines', 'faq', 'decisions')
HNSW = {'hnsw:space': 'cosine', 'hnsw:construction_ef': 200, 'hnsw:search_ef': 200}
# Vectors live in Chroma; ranking is exact cosine over the filter-eligible set (search.py).
DENSE_SEARCH = 'exact_cosine_over_chroma_stored_embeddings'

DEFAULTS = {
    'top_k': 8,
    'candidate_k': 30,        # Per path, chosen among filter-eligible chunks only.
    'rrf_k': 60,              # Reciprocal Rank Fusion constant.
    # Relevance weight; 1 - lambda weights redundancy. 0.65 removed relevant evidence on the
    # evaluation set (recall 0.52); 0.9 chosen 2026-10-29. use_mmr=False gives RRF only.
    'mmr_lambda': 0.9,
    'bm25_k1': 1.5, 'bm25_b': 0.75,
    'batch_scope': 'project',  # 'project' keeps earlier batches (marked); 'strict' keeps batch + project-wide.
    # 'current': applicable revision per lineage, applicable section supersession removed before
    # ranking. 'history': every revision, with its applicability marked (conflict research).
    'version_mode': 'current',
}
