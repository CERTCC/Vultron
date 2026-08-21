---
title: Role holder, receiving actor and store owner must be the same actor
type: learning
timestamp: 2026-08-19
source: ISSUE-2238
signal: design-invariant
---

A role-gated BT commit involves **three** separately-specified identities, and a
test (or a caller) that lets any two of them drift produces a silent skip rather
than an error:

1. **Who holds the role** — the `CVDRole.CASE_MANAGER` participant named in the
   case (`actor_participant_index`).
2. **Who receives the message** — `request.receiving_actor_id`.
3. **Whose store the tree runs in** — the DataLayer's `actor_id`, which since
   ADR-0069 is selected by the executing actor.

`CommitCaseLedgerEntryNode` is gated on (1) via `CheckIsCaseManagerNode` (CLP-09),
runs under (2) per BT-17-005, and reads/writes (3). When they disagree the gate
evaluates against an actor that holds no role, returns SUCCESS-by-skip, and no
ledger entry is written. Nothing raises.

**Observed in `test_embargo_ledger_cascade.py`**: the fixture named the
*coordinator* as CASE_MANAGER while the tests received as the *case actor*, so
every ledger assertion in the file was asserting a commit the fixture forbade.
Before per-actor stores this was invisible, because (3) did not exist as a distinct
fact.

**How to apply**: when a fixture names a role holder, derive the store and the
receiving actor from that same value rather than restating them
(`ledger_holder_id = case_manager_actor_id or case_actor_id`). If a test genuinely
needs the three to differ, it is testing the *skip* path and should assert the skip
— not a commit.

**Decided (maintainer, 2026-08-19): this becomes a normative entry in Phase 6**,
under `BT-05` alongside `BT-05-005` — the executing actor of a role-gated tree MUST
hold the gating role, and its store MUST be that actor's.

Rationale for a MUST rather than a note: this is the invariant that made the
delegated-emit defect class possible in the first place, and production satisfying
it *today* is not the same as it being required. Without a MUST, a future BT node
can re-separate the three identities and the failure mode is a silent skip.

An architecture ratchet was considered and rejected for now: role holding is
data-dependent, so a static check could only approximate it and would be noisy.
