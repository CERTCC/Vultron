---
source: INBOX-972-SPLIT
timestamp: '2026-06-22T19:34:36.882600+00:00'
title: Inbox policy must live in the core BT module, not the FastAPI router
type: learning
---

When adding new inbox processing logic (rehydrate step, defer gate, error
classification), the change belongs in `vultron/core/behaviors/inbox/` — not
the FastAPI router, not a new adapter-layer helper. `process_payload` is the
single caller-facing entry point; the BT is the only place policy can live
and remain testable from non-HTTP entry points. Adding an adapter helper
creates a shadow pipeline that bypasses the auditable tree and duplicates
dispatch logic, which is the original V-08 violation (ADR-0009).

**Promoted**: 2026-06-22 — captured in `AGENTS.md` (Inbox Policy Logic pitfall).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
