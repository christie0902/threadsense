"""Immutable content-addressed files: objects/<sha256[:2]>/<sha256>. A stored file is never rewritten; every read
recomputes its hash, so a corrupted or truncated file is reported and never returned as a result."""
from hashlib import sha256
import os
from pathlib import Path
import time
import uuid


class CacheCorruption(BaseException):
    """A stored file does not match its recorded hash. Never served, never silently replaced by a new request."""


class PersistenceFailure(BaseException):
    """A request or response could not be saved; nothing more is sent."""


def digest(data):
    return sha256(data).hexdigest()


class Store:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, sha):
        return self.root/sha[:2]/sha

    def put(self, data):
        data = bytes(data)
        sha = digest(data)
        path = self.path(sha)
        try:
            if path.exists():
                if digest(path.read_bytes()) != sha:
                    raise CacheCorruption(f'Stored object {sha} is corrupted; it is not overwritten.')
                return sha
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f'{sha}.{uuid.uuid4().hex}.tmp')  # Unique per write (worker threads).
            with temporary.open('xb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(6):  # Windows indexers can hold a fresh file briefly (README: WinError 5).
                try:
                    os.replace(temporary, path)
                    break
                except PermissionError:
                    if attempt == 5:
                        raise
                    time.sleep(0.5 * (attempt + 1))
        except CacheCorruption:
            raise
        except Exception as error:
            raise PersistenceFailure(f'Cannot save object {sha}: {type(error).__name__}: {error}') from error
        return sha

    def get(self, sha):
        path = self.path(sha)
        if not path.is_file():
            raise CacheCorruption(f'Stored object {sha} is missing.')
        data = path.read_bytes()
        if digest(data) != sha:
            raise CacheCorruption(f'Stored object {sha} does not match its hash.')
        return data

    def has(self, sha):
        return self.path(sha).is_file()
