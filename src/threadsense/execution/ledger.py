"""One durable, transactional execution and budget ledger per run (SQLite, shared by every process and stage).

A request row is written and committed before anything is sent (state RESERVED, its conservative maximum charge
reserved inside the same IMMEDIATE transaction that checks the hard ceiling), marked SENT just before the network
attempt, then SETTLED with the provider-reported cost, or left UNCERTAIN (charged at its full reservation) when the
outcome is unknown. Committed spending = settled charges + open reservations + uncertain reservations; it can never
exceed the ceiling, across processes and restarts. Rows are never deleted.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import functools
import sqlite3
import threading
import uuid

OPEN = ('RESERVED', 'SENT')
SCHEMA = '''
create table if not exists meta (key text primary key, value text not null);
create table if not exists requests (
  request_id text primary key, cache_key text not null, stage text, agent text, endpoint text, model text, origin text not null,
  state text not null, reserved_usd real not null default 0, charged_usd real not null default 0,
  request_sha text, response_sha text, http_status integer, usage text, returned_model text, provider_request_id text,
  cache_savings_usd real not null default 0, created_at text not null, sent_at text, settled_at text, error text);
create index if not exists requests_key on requests(cache_key);
'''


class BudgetExceeded(BaseException):
    """Reserving this request would exceed the hard ceiling: it is not sent."""


class LedgerError(BaseException):
    """The ledger could not record a request; nothing is sent."""


def now():
    return datetime.now(timezone.utc).isoformat()


def locked(method):
    """Agent frameworks call the provider from worker threads: one connection, used under one lock."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return wrapper


class Ledger:
    def __init__(self, path, limit_usd=None, *, readonly=False):
        self.path, self.lock = Path(path), threading.RLock()
        if readonly:
            self.db = sqlite3.connect(f'file:{self.path.as_posix()}?mode=ro', uri=True, isolation_level=None, timeout=30,
                                      check_same_thread=False)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=30, check_same_thread=False)
        self.db.execute('pragma journal_mode=wal')
        self.db.execute('pragma synchronous=full')
        self.db.executescript(SCHEMA)
        saved = self.meta('limit_usd')
        if saved is None:
            if limit_usd is None:
                raise LedgerError('A new ledger needs its hard ceiling.')
            self.db.execute('insert into meta values (?, ?)', ('limit_usd', json.dumps(limit_usd)))
        elif limit_usd is not None and json.loads(saved) != limit_usd:
            raise LedgerError(f'This run\'s ceiling is ${json.loads(saved)}; it cannot be changed to ${limit_usd}.')

    @locked
    def close(self):
        self.db.close()

    @locked
    def meta(self, key):
        row = self.db.execute('select value from meta where key = ?', (key,)).fetchone()
        return row[0] if row else None

    @property
    def limit_usd(self):
        return json.loads(self.meta('limit_usd'))

    @locked
    def committed_usd(self, db=None):
        (settled,) = (db or self.db).execute("select coalesce(sum(charged_usd), 0) from requests where state = 'SETTLED'").fetchone()
        (held,) = (db or self.db).execute(
            "select coalesce(sum(reserved_usd), 0) from requests where state in ('RESERVED', 'SENT', 'UNCERTAIN')").fetchone()
        return settled + held

    @locked
    def rows(self, cache_key=None):
        cur = self.db.execute('select * from requests' + (' where cache_key = ?' if cache_key else '') + ' order by created_at',
                              (cache_key,) if cache_key else ())
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]

    @locked
    def reserve(self, *, cache_key, stage, agent, endpoint, model, reserved_usd, request_sha):
        """Atomically check the ceiling and record the request before it is sent. Returns its request ID."""
        request_id = uuid.uuid4().hex
        try:
            self.db.execute('begin immediate')
            try:
                committed = self.committed_usd()
                if committed + reserved_usd > self.limit_usd + 1e-9:
                    raise BudgetExceeded(f'{stage}: reserving ${reserved_usd:.4f} would exceed the ${self.limit_usd:.2f} '
                                         f'ceiling (committed ${committed:.4f}); not sent.')
                self.db.execute('insert into requests (request_id, cache_key, stage, agent, endpoint, model, origin, state, '
                                'reserved_usd, request_sha, created_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                (request_id, cache_key, stage, agent, endpoint, model, 'FRESH_LIVE', 'RESERVED', reserved_usd,
                                 request_sha, now()))
                self.db.execute('commit')
            except BaseException:
                self.db.execute('rollback')
                raise
        except (BudgetExceeded, KeyboardInterrupt):
            raise
        except Exception as error:
            raise LedgerError(f'Cannot record the request: {error}') from error
        return request_id

    @locked
    def _update(self, sql, args):
        try:
            self.db.execute(sql, args)
        except Exception as error:
            raise LedgerError(f'Cannot update the ledger: {error}') from error

    @locked
    def mark_sent(self, request_id):
        self._update("update requests set state = 'SENT', sent_at = ? where request_id = ? and state = 'RESERVED'",
                     (now(), request_id))

    @locked
    def release(self, request_id, error):
        """Not sent (refused before the network attempt): the reservation is released."""
        self._update("update requests set state = 'NOT_SENT', reserved_usd = 0, error = ?, settled_at = ? where request_id = ?",
                     (error[:2000], now(), request_id))

    @locked
    def settle(self, request_id, *, http_status, response_sha, usage, charged_usd, returned_model, provider_request_id,
               savings_usd=0.0):
        """Provider outcome recorded. Unknown cost keeps the full reservation (state UNCERTAIN, charged as reserved)."""
        if charged_usd is None:
            self._update("update requests set state = 'UNCERTAIN', http_status = ?, response_sha = ?, usage = ?, returned_model = ?, "
                         "provider_request_id = ?, settled_at = ?, error = ? where request_id = ?",
                         (http_status, response_sha, json.dumps(usage), returned_model, provider_request_id, now(),
                          'usage not reported; full reservation kept', request_id))
            return
        self._update("update requests set state = 'SETTLED', http_status = ?, response_sha = ?, usage = ?, charged_usd = ?, "
                     "returned_model = ?, provider_request_id = ?, cache_savings_usd = ?, settled_at = ? where request_id = ?",
                     (http_status, response_sha, json.dumps(usage), charged_usd, returned_model, provider_request_id,
                      savings_usd, now(), request_id))

    @locked
    def mark_uncertain(self, request_id, error):
        self._update("update requests set state = 'UNCERTAIN', error = ?, settled_at = ? where request_id = ? and state in "
                     "('RESERVED', 'SENT')", (error[:2000], now(), request_id))

    @locked
    def record_reuse(self, *, cache_key, stage, agent, endpoint, model, origin, request_sha, response_sha, http_status, usage):
        """A response served from saved artifacts: no request, no charge."""
        self._update('insert into requests (request_id, cache_key, stage, agent, endpoint, model, origin, state, request_sha, '
                     "response_sha, http_status, usage, created_at, settled_at) values (?, ?, ?, ?, ?, ?, ?, 'REUSED', ?, ?, ?, ?, ?, ?)",
                     (uuid.uuid4().hex, cache_key, stage, agent, endpoint, model, origin, request_sha, response_sha, http_status,
                      usage, now(), now()))

    @locked
    def recover(self):
        """After an interruption: requests left RESERVED or SENT have an unknown outcome. They become UNCERTAIN (charged
        in full) and are never resent automatically. Returns their IDs."""
        stale = [r['request_id'] for r in self.rows() if r['state'] in OPEN]
        for request_id in stale:
            self.mark_uncertain(request_id, 'process stopped before the outcome was recorded; not resent')
        return stale

    @locked
    def summary(self):
        rows = self.rows()
        by = {}
        for r in rows:
            k = (r['stage'], r['origin'], r['state'])
            e = by.setdefault(k, {'stage': r['stage'], 'origin': r['origin'], 'state': r['state'], 'requests': 0,
                                  'charged_usd': 0.0, 'reserved_usd': 0.0, 'cache_savings_usd': 0.0})
            e['requests'] += 1
            e['charged_usd'] += r['charged_usd']
            e['reserved_usd'] += r['reserved_usd'] if r['state'] == 'UNCERTAIN' else 0
            e['cache_savings_usd'] += r['cache_savings_usd']
        return {'limit_usd': self.limit_usd, 'committed_usd': round(self.committed_usd(), 6), 'rows': len(rows),
                'by_stage': sorted(by.values(), key=lambda e: (e['stage'] or '', e['origin'], e['state']))}
