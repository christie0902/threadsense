"""Shared execution layer for full ThreadSense runs: one budget ledger and one response store across Agent 1, Agent 2
and Agent 3, enforced at the HTTP transport every agent already uses (no change to agent code or prompts).

- pricing: provider list prices for the exact models in use and the conservative per-request reservation.
- store: immutable content-addressed files (requests, raw responses), verified on every read.
- ledger: one transactional SQLite ledger per run (reservations, settlements, request identity and origin).
- guard: the transport hook (httpx for CrewAI/LiteLLM/OpenAI SDK; verification_requests.send_once for the
  single-attempt transport): reserve, persist, send once, persist the raw response, settle.
- pipeline: stage boundaries (snapshot, Agent 1, grouping, Agent 2, Agent 3, finalize) with artifact manifests.
"""
