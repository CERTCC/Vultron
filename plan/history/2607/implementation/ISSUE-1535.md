---
source: ISSUE-1535
timestamp: '2026-07-20T18:52:47.227934+00:00'
title: FVCV-extension demo — four-actor CVD scenario
type: implementation
---

## Issue #1535 — FVCV-extension demo

Implemented the four-actor CVD coordination demo with a new `accept-actor-recommendation` trigger endpoint.

Key work:

- Full hexagonal trigger stack for `Accept(Offer(CaseParticipant))` — BT node → factory → use case → service → FastAPI
- `EmitAcceptCaseParticipantOfferNode` in `suggest_actor/emit.py` (kept `actor.py` under 500-line limit)
- `seed_containers_fvcv` (4 containers, 12 cross-registrations)
- Full demo script `fvcv_extension_demo.py` (puppeteering pattern — uses real trigger endpoints)
- CLI command + CI job + 8 unit tests

PR: <https://github.com/CERTCC/Vultron/pull/1540>
