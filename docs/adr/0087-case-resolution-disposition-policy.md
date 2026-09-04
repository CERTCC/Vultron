---
status: accepted
date: 2026-09-03
deciders: Allen D. Householder
consulted:
informed:
---

# Case-Resolution Disposition for BT Nodes Is Chosen by Role, Not Re-Decided Per Call Site

## Context and Problem Statement

Dozens of behavior-tree (BT) nodes resolve a `VulnerabilityCase` from the
DataLayer with `datalayer.read_case(case_id)` and then must decide what to do
when the lookup returns nothing. A census of the `vultron/core/behaviors/`
tree (#3101) found that lookup open-coded at ~78 call sites, each having
independently re-invented the "case evaporated underneath me" branch. The
dispositions had drifted apart along two axes that no design ever reconciled:

- **Verdict on absence.** Some sites returned `FAILURE`, some `SUCCESS`, some
  fell through with an empty result — with no principle distinguishing them.
- **Loudness.** Among the `FAILURE` sites, the log level ranged over silent,
  `debug`, `warning`, and `error`, and the `feedback_message` text was
  bespoke at every site (or absent).

This drift was not merely cosmetic. Concern #3101 traced a real defect to it:
`FilterCsEmDimensionNode` returning `FAILURE` on a missing case short-circuited
the `memory=False` Sequence and left `BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE` stale
on the process-global blackboard, so a subsequent execution could commit a
ledger entry against another case's override payload. The bug was possible only
because "what to do when a case disappears" lived at the call site instead of
in one shared place.

The question this ADR settles: **when a BT node cannot resolve the case it was
told to coordinate, what is the correct disposition — and where does that
decision live?**

## Decision Drivers

- One canonical decision about case-absence, not a per-site accident (#3101).
- DRY: a single implementation activated from everywhere that needs it, with
  no parallel implementations of the same idea.
- Error handling should clean up when an error occurs; teardown hygiene must
  not depend on which node happened to short-circuit a Sequence.
- The default must be safe: continuing to coordinate a case that does not
  exist is almost never legitimate.
- Genuine exceptions (partial replicas, cases mid-construction) must remain
  expressible without reopening the default.

## Considered Options

- **A. Leave dispositions at each call site** (status quo) — document a
  convention and hope new nodes follow it.
- **B. One helper, one disposition** — force every site to hard-fail through a
  single function.
- **C. Role-indexed disposition helpers** — a small closed set of
  dispositions, each with one shared entry point, chosen by the node's role.

## Decision Outcome

Chosen option: **C, role-indexed disposition helpers.** Absence-of-case is not
one situation but a small, closed set of them, distinguished by the node's role
in the protocol. Each disposition gets exactly one shared implementation, and a
node selects its disposition by *which helper it calls* — never by re-deciding
the branch inline. Option B is too blunt (it would break legitimate
replica-apply and case-under-construction flows); option A (status quo) is what
produced the defect reported in #3101.

There are **three regimes** plus one explicitly-documented lenient pattern:

### Regime 1 — Authoritative coordination (the default)

Guards, per-dimension filters, ledger commits, append/emit nodes: the case
**must** exist. Its absence mid-coordination is an anomaly — a concurrent
deletion or a caller bug — never a routine branch. These nodes call

```python
case, failure = self._require_case(self.case_id)
if failure is not None:
    return failure
# `case` is a VulnerabilityCase from here on
```

`require_case` (in `vultron/core/behaviors/helpers.py`, exposed as the
`_require_case` method on all four BT base classes) reports one canonical
outcome: `Status.FAILURE`, logged at `error`, with a canonical
`feedback_message` of `case '{case_id}' not found in DataLayer`. Its isinstance
guard treats a non-`VulnerabilityCase` record as not-found, subsuming the
defensive type checks several sites had hand-rolled.

A node that legitimately has *no* case to act on (an absent/empty `case_id`,
meaning "nothing to coordinate") returns `SUCCESS` **before** calling
`_require_case`. The distinction is deliberate: *absent `case_id`* = nothing to
do (SUCCESS); *present `case_id`, missing case* = anomaly (FAILURE).

### Regime 2 — Replica-apply of a remote ledger entry

Apply-from-ledger nodes (`sync/nodes/*_effect.py`, best-effort signatory seeds)
run against a **partial local replica** whose case row may legitimately be
absent (SYNC-02-002, ADR-0073 per-actor storage). Absence here is normal: the
local store simply does not mirror that case yet. These nodes call

```python
case = self._resolve_case_replica(case_id)
if case is None:
    return Status.SUCCESS  # skip the apply; do not block Announce processing
```

`resolve_case_replica` logs at `debug` and sets no failure `feedback_message`.
It is the same lookup as Regime 1 with the opposite verdict on absence.

### Regime 3 — Case-under-construction

Proposal / offer-received flows read the case precisely to discover whether it
exists *yet*, then create it. Absence legitimately precedes a create, so these
nodes handle the `None` inline and use neither helper. They are marked in code
and allowlisted by the conformance guard (below).

### Lenient guards (documented, not a fourth helper)

A few skip-condition nodes are inverted: `SUCCESS` means "nothing to do here."
For these, a missing case is one more "nothing to do" case and returning
`SUCCESS` is correct (e.g. optional-enrichment emits, best-effort diagnostics).
These remain inline, are commented as lenient, and are allowlisted.

### Module-level resolvers (documented, not a fourth helper)

A handful of shared lookups are plain module functions that take a bare
`datalayer`/`dl` rather than a BT node (e.g. `_resolve_actor_roles`,
`_create_and_attach_participant`). They cannot call `self._require_case`, so
they resolve the case directly and signal absence by returning `None`; the
*calling node* then produces the Regime-1 `FAILURE`. This preserves the
single-verdict outcome while keeping the resolver reusable across nodes. They
are commented as module-resolvers and allowlisted.

### Audit records are best-effort, not a coordination precondition

One class of write — appending a **native ledger entry** whose sole purpose is
an audit record (`_CommitNativeLedgerEntriesNode`) — is deliberately *not*
Regime 1. If the case is absent the entry has nothing to attach to, but the
absence is handled downstream where it matters: the paired create-case marker
node hard-fails on an absent case (Regime 1), so coordination still stops. The
ledger append itself therefore skips as `SUCCESS` rather than double-reporting
the same anomaly. This is commented as audit-best-effort and allowlisted;
critically, a case that *exists* but whose genesis commit fails is still a
`FAILURE` (the distinction is case-absent vs. commit-failed, not lenience).

## The #3101 blackboard carve-out (CONCERN-2711 / BT-17-003)

The disposition policy fixes *who decides*; it does not by itself clean up
blackboard state a short-circuited node left behind. Those are handled by a
separate, complementary rule about **key ownership and lifetime**:

- **Within-tick shared keys** (e.g. the CS dimension-filter accumulator) are
  cleared by their *owning* node at tick start (BT-17-003). A node must **not**
  zero a shared key it does not own (CONCERN-2711) — doing so corrupts a peer.
- **Cross-execution hand-off keys** such as `BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE`
  are *execution-scoped*: written mid-tree by a producer and consumed by a
  later node in the same `execute_with_setup` run. No single node can own their
  cleanup on every path (a Sequence short-circuit skips the consumer). These
  keys are therefore listed in `BTBridge.execute_with_setup`'s `managed_keys`
  and reset to their pre-execution state in the `finally` block on **every**
  outcome. Whatever execution wrote the override has it reset at its own
  teardown, so no execution leaks it forward regardless of which node
  short-circuited — closing #3101 without any node re-deciding cleanup.

## Consequences

- Good: one place defines each disposition; adding a Regime-1 node cannot
  re-drift the loudness or verdict of case-absence.
- Good: #3101's stale-override class of bug is structurally prevented — teardown
  hygiene no longer depends on the short-circuit path.
- Good: the two principled exceptions (partial replica, case-under-construction)
  stay expressible and are visible as *deliberate* choices, not omissions.
- Bad / accepted cost: nodes that formerly SUCCESS-skipped on a missing case now
  hard-fail (e.g. the pre-filter CS invariant guards). This is the intended
  behavior change; a present-but-unresolvable `case_id` is an anomaly. Tests
  asserting the old lenient contract were updated.
- Neutral: `require_case` and `resolve_case_replica` are the same lookup; the
  only difference is disposition, so the duplication is a verdict, not code.

## Validation

A conformance guard under `test/architecture/` scans `vultron/core/behaviors/`
for hand-rolled `read_case(...) → None → Status.*` dispositions and fails on any
site that is neither one of the two shared helpers nor on the allowlist of
sanctioned exceptions (Regime-2 replica/seed, Regime-3 case-under-construction,
lenient guards, module-level resolvers, and audit-best-effort ledger appends),
each carrying a category comment at its call site. The allowlist is exact — a
new direct `read_case` site *or* a stale allowlist entry both fail the guard —
so new drift fails CI rather than accumulating silently, the way the #3101
census showed it had
(`test/architecture/test_case_resolution_uses_helpers.py`).

## More Information

- Concern #3101 — the stale-override defect that motivated the census.
- CONCERN-2711 / BT-17-003 — blackboard key ownership and tick-start clearing.
- ADR-0073 — per-actor storage / partial replicas (Regime 2 rationale).
- SYNC-02-002 — replica-apply skip on absent local case.
- `notes/bt-pitfalls.md` — the tick-boundary carve-out, cross-referenced.

Generated spec requirements: none (structural policy; enforced by the
`test/architecture/` conformance guard rather than per-change spec IDs).
