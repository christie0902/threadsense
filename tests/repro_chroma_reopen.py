"""Reproducer (not collected by pytest): build a test-double index in a fresh temp dir, then open it in-process.

  uv run --locked python tests/repro_chroma_reopen.py VARIANT N ROOT

VARIANT current   repository code (the build closes its Chroma client before verifying and reopening)
VARIANT unclosed  the pre-fix lifecycle: the build's client stays in Chroma's per-path system cache and the
                  in-process Retriever reuses it
Each iteration uses its own directory under ROOT (keep ROOT short and outside the repo on Windows). Prints one
JSON line per iteration and a summary. Measured 2026-10-29 (ChromaDB 1.5.9, Windows): unclosed failed 10/320
cycles with "Error creating hnsw segment reader: Nothing found on disk" (also without the subprocess check);
closed 0/260.
"""
import json
from pathlib import Path
import sys
import tempfile
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from threadsense.retrieval import index as index_mod  # noqa: E402
from threadsense.retrieval.index import build_index  # noqa: E402
from threadsense.retrieval.search import Retriever  # noqa: E402
from tests.retrieval_doubles import HashEncoder  # noqa: E402


def main(variant, n, root):
    root.mkdir(parents=True, exist_ok=True)
    if variant == 'unclosed':
        original = index_mod.chroma_client

        def unclosed(path):
            client = original(path)
            client.close = lambda: None  # Keep the build's system cached, as `del client` did.
            return client
        index_mod.chroma_client = unclosed
    elif variant != 'current':
        raise SystemExit(f'Unknown variant {variant!r}')
    failures = 0
    for i in range(n):
        path = Path(tempfile.mkdtemp(prefix=f'{variant}{i}_', dir=root))/'index'
        started = time.perf_counter()
        try:
            build_index(path, encoder=HashEncoder())
            Retriever(path, encoder=HashEncoder())
            status, detail = 'OK', None
        except Exception as error:  # noqa: BLE001 - every failure is recorded
            failures += 1
            status, detail = 'FAIL', ''.join(traceback.format_exception(error))[-1500:]
        print(json.dumps({'variant': variant, 'i': i, 'status': status, 'seconds': round(time.perf_counter() - started, 2),
                          'detail': detail}), flush=True)
    print(json.dumps({'variant': variant, 'iterations': n, 'failures': failures}), flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])))
