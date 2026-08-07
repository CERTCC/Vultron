---
source: ISSUE-2016
timestamp: '2026-08-07T19:21:44.152932+00:00'
title: 'AC-5a/5b/5c: ownership-transfer BT node and integration tests'
type: implementation
---

## Issue #2016 — AC-5a/5b/5c: BT node and integration tests for CaseActor routing

Implemented three acceptance criteria for ownership-transfer routing coverage.

**AC-5a/5b** (unit, `test_actor_and_announce_nodes.py`): New `TestEmitOwnershipTransferNodes` class verifies `EmitOfferCaseOwnershipTransferNode` and `EmitAcceptCaseOwnershipTransferNode` both route to `case_actor_id` via `to=` (ADR-0053 / CM-21-005/006).

**AC-5c** (integration, `test_fvcv_handoff_demo.py`): Three-actor `_TestClientRouter` test (Vendor / Coordinator / Finder). After POSTing `Accept(Offer(VulnerabilityCase))` to Coordinator's inbox, Finder's DataLayer receives `Announce(CaseLedgerEntry[event_type=accept_case_ownership_transfer])` — no manual trigger.

**Bugs fixed along the way:**

- `ACCEPT_CASE_OWNERSHIP_TRANSFER` was missing `include_activity=True` in the semantic registry — caused `event.activity=None`, empty payload snapshot, `VultronCanonicalEntryError` aborting `AcceptOwnershipTransferBT` for all HTTP-inbox deliveries
- Both `OfferCaseOwnershipTransferReceivedUseCase` and `AcceptCaseOwnershipTransferReceivedUseCase` lacked the `trigger_activity` kwarg injected by the dispatcher (both are in `_SYNC_AND_TRIGGER_PORT_SEMANTICS`)

PR: <https://github.com/CERTCC/Vultron/pull/2083>
