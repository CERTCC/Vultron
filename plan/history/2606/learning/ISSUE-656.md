---
source: ISSUE-656
timestamp: '2026-06-11T18:38:04.643870+00:00'
title: 'DataLayer scope regression tests: call_args.args and direct function testing'
type: learning
---

## 2026-06-11 ISSUE-656 — DataLayer scope regression tests

- Testing get_canonical_actor_dl() directly (as a plain Python function
  rather than through FastAPI DI) is straightforward: call it with explicit
  keyword args `actor_id=...` and `dl=...`.
- The AC-3a failure-mode test is intentionally asymmetric: the short-ID DL
  must see an empty outbox while the canonical-URI DL sees the entry. This
  documents the BUG-2026040901 scenario without requiring monkeypatching.
- Use `call_args.args` (Python 3.8+ attribute) rather than `call_args[0]`
  when asserting mock positional args — the named attribute fails clearly
  if the call shifts to kwargs; the index subscript returns an empty tuple
  silently.

**Promoted**: 2026-06-11 — captured in `AGENTS.md` pitfall "DataLayer Scope
Tests: Use call_args.args, Not call_args[0]". Surrogate-key collision
handling captured in `notes/codebase-structure.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
