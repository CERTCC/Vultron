---
source: CONCERN-1723
timestamp: '2026-07-28T20:18:38.661079+00:00'
title: Remove outmoded ASGI delivery path in favour of httpx
type: learning
---

## Original Concern

Two parallel message-delivery paths (httpx and ASGI) were believed to coexist,
with httpx as the current standard and the ASGI path as outmoded/dead legacy
predating an httpx migration. The concern asked to eradicate the ASGI path from
code, specs, notes, AGENTS.md, and ADRs.

## Investigation — Premise Inverted

Code investigation contradicted the framing: `ASGIEmitter` is the *current
production default* (wired via `configure_default_emitter` in both `main.py`
and `app.py` lifespans), and **both** delivery tiers already use httpx
(`ASGIEmitter` uses `httpx.ASGITransport`; `DemoHttpDeliveryAdapter` uses
`httpx.AsyncClient`). There is no pre-httpx "ASGI path" to delete — ASGI
transport *is* an httpx feature. The `ASGIEmitter` is also load-bearing:
CaseActor canonical-ledger self-delivery relies on `cc:`-to-self ASGI
routing (CLP-10-001).

## Resolved Intent

The real defect: the in-process ASGI shortcut makes co-located delivery behave
differently from remote delivery, masking inter-actor delivery bugs and giving
false confidence in demos where actors are meant to be autonomous, independent
peers (AKM-01). Decision (grill session): eliminate the special case and
deliver **all** inter-actor comms over the REST inbox/outbox HTTP API — "act as
if every recipient is remote." Application code must not use
`httpx.ASGITransport` directly except via FastAPI's `TestClient`. CaseActor
self-delivery becomes HTTP loopback.

**Resolved**: 2026-07-28 — planning complete; implementation tracked in #1779
(test-infra rewire, lands first) and #1780 (retire ASGIEmitter; HTTP sole
path, blocked-by #1779). Both are children of epic #1676.

**Docs PR**: <https://github.com/CERTCC/Vultron/pull/1778>
**ADR**: docs/adr/0041-http-only-inter-actor-delivery.md
**Spec**: specs/outbox.yaml OX-12 (supersedes specs/architecture.yaml ARCH-17)
**Notes**: notes/architecture-adapters.md
