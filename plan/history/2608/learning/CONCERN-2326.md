---
source: CONCERN-2326
timestamp: '2026-08-20T15:45:07.755488+00:00'
title: ledger_payload_object_override producer/consumer contract
type: learning
---

## What the concern identified

`ledger_payload_object_override` had no explicit spec contract. Any BT node
could publish an arbitrary dict and `CommitCaseLedgerEntryNode` would apply
it to the canonical hash-chained ledger entry without validating field names
or knowing where the patch came from. ISSUE-2256 (EM adjudication) would add
a second producer before any contract existed.

## Decisions made

**Override shape** (RSH-05-011): `{"object_id": …, "producer_type": <str>, "fields": {…}}`.
`producer_type` was added to enable per-producer audit logging and diagnostics;
multiple producers are anticipated.

**No-op clear** (RSH-05-010): producers MUST write `None` unconditionally at
the start of every tick before any early return. The py_trees blackboard is
process-global and `BTBridge.execute_with_setup` does not reset
application-level keys between runs. A producer that only writes on active
paths leaves stale values for `CommitCaseLedgerEntryNode` to apply to a
different payload snapshot on the next call. BT-17-003.

**Field-name allowlist** (RSH-05-012, RSH-05-013): producers MUST use only
recognized wire aliases; `CommitCaseLedgerEntryNode` MUST hard-fail (not warn)
on any unrecognized key. An unknown alias applied to the canonical snapshot
would silently corrupt the ledger entry replicated to all participants.

**producer_type validation** (RSH-05-014): consumer SHOULD warn on unknown
`producer_type` but MUST NOT fail the commit. Field-name validation is the
data-integrity guard; `producer_type` is an audit hint.

**ADR determination**: spec entries only — RSH-05-009 already captures the
field-patch-not-replacement rationale; no new ADR needed.

**Typed Ports forward pointer**: ISSUE-1808 (typed-Ports base class for BT
nodes) could make the no-op clear structural if the base class auto-clears
declared output ports in `initialise()`. This connection is captured in
RSH-05-010 and the AGENTS.md pitfall; ISSUE-1808 authors should consider it.

## What was produced

- RSH-05-010 through RSH-05-014 added to `specs/received-status-handling.yaml`
- `notes/received-status-authorization.md` updated with new override shape and
  producer/consumer contract summary
- `AGENTS.md` pitfall added: `ledger_payload_object_override` producer contract
- Docs PR: <https://github.com/CERTCC/Vultron/pull/2431>
- Impl tasks: #2432 (enforce contract in code, size:M), #2433 (update ISSUE-2256 with contract reference, size:S)
