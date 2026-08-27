# AGENTS.md — `vultron/core/behaviors/embargo/`

Agent guidance for embargo-related BT nodes and subtrees in this package.

> For project-wide BT conventions see
> [`vultron/core/behaviors/AGENTS.md`](../AGENTS.md).

---

## Embargo Subtree Idempotency with Blackboard Flag

(ISSUE-750, 2026-06-08)

When a god node is decomposed into a sequence of leaf nodes, the original
single-pass semantics may break if duplicate-run behavior depended on the
god node's internal guard. Preserve idempotency explicitly:

- Add a blackboard flag (e.g., `embargo_initialized: bool`) that is set
  to `True` only when the current execution actually created a new embargo.
- Side-effect leaves that should only fire on first initialization (e.g.,
  seeding participants, creating events) MUST check this flag before
  acting.
- When moving EM transition logic to `EmbargoLifecycle.propose_embargo`,
  keep event creation and participant-seeding behavior aligned with
  existing duplicate-report tests to avoid introducing regressions.

---

## Routing-Gated State Mutation

(BT-19, 2026-06-26; see `specs/behavior-tree-integration.yaml` BT-19-001,
BT-19-002)

A BT Sequence that performs a protocol state-machine transition (EM, RM, or CS)
and then routes an outbound activity MUST resolve all routing prerequisites
in a read-only guard node placed **before** the state-mutation node.

**Why ordering matters**: Once the DataLayer accepts a state write (e.g.,
`EM=EXITED`), the transition is committed. If the subsequent routing step
then fails (missing Case Manager, missing factory), the outbound notification is
never sent. Peers retain the prior state; local state has advanced — a
divergence window that requires ledger-sync catch-up (SYNC-10) to repair.
Moving the routing guard to the top of the Sequence eliminates the divergence:
if routing prerequisites are absent, the tree returns `FAILURE` with zero
DataLayer state change.

**Shared factory requirement**: Duplicated monolithic BT nodes that inline both
state mutation and dispatch in a single `update()` method drift independently.
The canonical factory-composed path may correctly order the guard, while the
automatic-cascade monolith retains the old unsafe ordering, reintroducing the
divergence bug on that path only. All call sites for the same lifecycle
transition MUST use a shared BT factory function (BT-19-002).

**Canonical Sequence structure**:

```text
Sequence
├── ResolveCaseManagerNode          ← read-only guard; FAILURE = bail, no write
├── <StateTransitionNode>           ← mutation committed after guard passes
└── <SendDispatchNode>              ← routing succeeds because guard already verified
```

**Anti-pattern** (Issue #1054 — `TerminateEmbargoNode`):

```text
Sequence
├── TerminateEmbargoLifecycleNode   ← mutation committed first ← ❌
└── SenderSideBT                    ← routing checked second; fail = divergence
```

**Fix**: Extract a shared factory (`terminate_embargo_bt`) that places
`ResolveCaseManagerNode` before `TerminateEmbargoLifecycleNode`, and replace
all standalone monolithic nodes with the factory output. Both trigger and
cascade call sites use the shared factory directly (BT-19-002, PR #1263).
