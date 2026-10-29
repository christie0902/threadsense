"""Build the local retrieval index (Chroma + sidecar) from the knowledge store and demo fixture.

Offline by default: the embedding model must already be in the local Hugging Face
cache. --allow-download permits a one-time setup download. No paid calls. Source
files are only read. An identical rebuild is a no-op; a changed corpus or
configuration requires --rebuild, which replaces the three collections.
"""
import argparse
import json
from pathlib import Path
import sys

from threadsense.retrieval.config import FIXTURE_CUTOFF, FIXTURE_ROOT, INDEX_DIR, KNOWLEDGE_ROOT


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--index-dir', type=Path, default=INDEX_DIR)
    parser.add_argument('--knowledge-root', type=Path, default=KNOWLEDGE_ROOT)
    parser.add_argument('--fixtures', type=Path, default=FIXTURE_ROOT)
    parser.add_argument('--cutoff', default=FIXTURE_CUTOFF)
    parser.add_argument('--rebuild', action='store_true', help='Replace an index built from a different corpus/config.')
    parser.add_argument('--allow-download', action='store_true', help='Permit fetching the pinned embedding model (setup only).')
    parser.add_argument('--plan', action='store_true', help='Normalize and chunk only; no embeddings, no index writes.')
    args = parser.parse_args(argv)
    from threadsense.retrieval.embeddings import SentenceEncoder
    from threadsense.retrieval.index import RetrievalIndexError, build_index, plan
    try:
        encoder = SentenceEncoder(allow_download=args.allow_download)
    except OSError as error:
        parser.error(f'Embedding model unavailable offline ({error}). Run once with --allow-download.')
    sources = {'knowledge_root': args.knowledge_root, 'fixture_root': args.fixtures, 'cutoff': args.cutoff}
    if args.plan:
        chunks, documents, corpus, core = plan(encoder, **sources)
        print(json.dumps({'documents': len(documents), 'chunks': len(chunks), 'corpus_fingerprint': core['corpus_fingerprint']}, indent=2))
        return 0
    try:
        manifest = build_index(args.index_dir, encoder=encoder, rebuild=args.rebuild, **sources)
    except RetrievalIndexError as error:
        parser.error(str(error))
    keys = ('status', 'documents', 'chunks', 'collection_documents', 'collection_chunks', 'split_documents',
            'max_chunk_tokens', 'embedding', 'corpus_fingerprint', 'build_fingerprint')
    print(json.dumps({k: manifest[k] for k in keys} | {
        'current_day_announcements': {k: manifest['corpus']['current_day_announcements'][k] for k in (
            'announcement_threads', 'extracted', 'with_inherited_agent1', 'extraction_failures')},
        'index_dir': str(args.index_dir)}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
