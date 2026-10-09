---
source: CONCERN-4004
timestamp: '2026-10-01T16:29:50.973392+00:00'
title: Replica lacking the replaced embargo's record is unreachable once the activation
  writers fail closed
type: learning
---

## Summary

Since ADR-0093 the owner's activation of revision B is where consent is re-evaluated, and the A-vs-B comparison (`_revision_ends_no_later`) reads both `EmbargoEvent` records and fails closed on an unreadable one (EP-08-002's read path). A replica that never received embargo A's record therefore cannot apply the owner's `Accept(Invite(EmbargoEvent B))`: `accept_embargo_invite` raises `VultronNotFoundError`, `RecordParticipantAcceptanceNode` reports FAILURE and the replica's EM stays `REVISE` with `active_embargo = A`. Before ADR-0093 the EM/`active_embargo` sync happened regardless. The same shape exists in `SetEmbargoActiveNode` (`activate_embargo`, the ledger replay path).

## What PR #4002 does

The received Accept use case reports `DEFERRED` (parked for replay, HP-01-003) rather than `REFUSED` when the node's feedback carries `REPLACED_EMBARGO_UNREPLICATED_PREFIX` — i.e. when the *replaced* embargo, not the accepted one, is the record missing. An Accept naming an embargo the case has never seen stays `REFUSED`.

## What remains

Nothing re-drives a deferred inbox item when a missing *object* (rather than the case) later arrives: `DispatchNode._replay_after_bootstrap` replays only after a case bootstrap. A replica that is missing A needs either (a) a catch-up that fetches A (a driven port for object retrieval does not exist), or (b) a replay trigger when an `EmbargoEvent` is stored, or (c) the ledger snapshot for the activation to carry A's `end_time` so the comparison needs no second read. Whether such a replica is reachable in practice — every path that sets `active_embargo` persists the record first — should be settled before a mechanism is built.

## Reference

Source: review of PR #4002
ADR: `docs/adr/0093-signatory-declined-pec-transition.md` (revised 2026-09-29)
Specs: EP-05-001, EP-08-002, HP-01-003, SYNC-14, SYNC-15

**Resolved**: 2026-10-01 — implementation tracked in #4032 (and #3915 AC-5). Planning found the replica unreachable on every current path except the activation writers never reading the embargo they activate; EMB-18-003 closes that and retires the DEFERRED arm instead of building a catch-up mechanism.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4033>.
Spec: `specs/em-behavior.yaml` (EMB-18-003).
Notes: `notes/embargo-lifecycle.md`.
