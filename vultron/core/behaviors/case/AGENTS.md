# AGENTS.md — `vultron/core/behaviors/case/`

Agent guidance for case-management BT nodes and subtrees in this package.

> For project-wide BT conventions see
> [`vultron/core/behaviors/AGENTS.md`](../AGENTS.md).

---

## Guarded Commit: Role-Gated Canonical Writes

(ISSUE-1021, 2026-06-17; see `specs/case-ledger-processing.yaml` CLP-09 and
`notes/case-ledger-authority.md` § "Commit Authorization and Coverage")

Any canonical-write node (e.g., `CommitCaseLedgerEntryNode`) that may be
reached from more than one actor context MUST be wrapped in a role-gated
`Selector`, never invoked bare:

```python
Selector(
    name="GuardedCommitCaseLedgerEntry",
    memory=False,
    children=[
        Sequence(
            children=[
                CheckIsCaseManagerNode(case_id=case_id),
                CommitCaseLedgerEntryNode(case_id=case_id),
            ]
        ),
        py_trees.behaviours.Success(
            name="CommitCaseLedgerEntrySkippedNotCaseManager"
        ),
    ],
)
```

`CheckIsCaseManagerNode` resolves the case's `CVDRole.CASE_MANAGER`
participant and compares it against the *actor active for this invocation* —
never against the use-case class's identity, and never assumed from a previous
invocation having passed.

Wrap the pattern once as a reusable factory (e.g.
`create_guarded_commit_case_ledger_entry_tree(case_id=None)`) rather than
re-inlining the Selector at each call site; CLP-09-002 requires a test
asserting no bare usage remains outside it.

**`execute()` MUST do nothing but build one tree, run it once, and handle
the result** (ADR-0022, CLP-10-005): a received-side use case's `execute()`
method MUST (a) build exactly one BT via a tree-factory function in
`vultron/core/behaviors/`, (b) call `BTBridge.execute_with_setup()` exactly
once, and (c) handle the result. The guarded-commit factory MUST be composed
as a child of that one tree, not invoked separately. See CLP-09-004.

---

## Role Guard Required for All CASE_MANAGER-Only BT Subtrees

(ISSUE-1030, 2026-06-18; see `specs/behavior-tree-integration.yaml` BT-17-001,
BT-17-002)

`CheckIsCaseManagerNode` MUST be applied to **any** BT subtree whose
semantics are restricted to the `CVDRole.CASE_MANAGER` actor, not only
`CommitCaseLedgerEntryNode`. The canonical composite:

```python
Selector(
    name="ActionIfCaseManager",
    memory=False,
    children=[
        Sequence(
            name="CaseManagerGuardedAction",
            children=[
                CheckIsCaseManagerNode(case_id=case_id),
                ActionNode(case_id=case_id),
            ],
        ),
        py_trees.behaviours.Success(name="ActionSkippedNotCaseManager"),
    ],
)
```

**Why this is necessary**: Received-side use cases run the BT with the
receiving actor's `actor_id`. Without an in-tree role guard, a
CASE_MANAGER-only node fires for every receiving actor. Placing the guard
outside the tree (e.g., in `execute()`) is insufficient because the same tree
factory may be shared across trigger-side and received-side paths.

---

## Ledger Commit Must Precede Outbox Write

(ISSUE-1325, 2026-07-13)

When a BT subtree both commits a ledger correlation marker and records an
outbox item, the ledger commit MUST happen first.

If the outbox write happens first and the ledger commit subsequently fails,
the outbox item is orphaned: an activity queued for delivery with no
corresponding ledger entry. On the next invocation, the duplicate-detection
guard finds no pending entry and takes the "fresh" path, triggering a
duplicate offer or invite.

Correct ordering:

1. Build activity via factory (creates the object in the DataLayer)
2. Commit ledger correlation marker (fail-fast if anything is wrong)
3. Record outbox item (reached only if ledger commit succeeded)

This invariant is enforced by CLP-10-006 in `specs/case-ledger-processing.yaml`.

---

## Use `disposition="rejected"` for Local-Only Ledger Correlation Markers

(ISSUE-1325, 2026-07-13)

When a BT node needs a local ledger entry that does NOT correspond to a
canonical AS2 activity (e.g., tracking an outbound `offer_case_participant`
for duplicate detection), use `disposition="rejected"` in
`create_commit_log_entry_tree`.

`_validate_canonical_entry` returns early for non-`"recorded"` dispositions,
bypassing the `_CANONICAL_PAYLOAD_SIGNATURES` allowlist check. The entry is
still persisted and `find_protocol_pair` does not filter on disposition, so
the correlation marker remains visible to duplicate-detection nodes.

---

## Idempotency Guards Must Be Silent — No Ledger Write on Duplicate

(CONCERN-1754, 2026-08-05)

`disposition="rejected"` is valid for **emit-side correlation markers** (see
above). It is **not** valid for **idempotency guard no-ops**.

An idempotency guard is a `DataLayerCondition` node that detects "this event
was already processed" and returns `Status.FAILURE` to abort the tree. When
a guard fires, **no ledger entry of any disposition must be written**
(CLP-13-001). Use only `logger.info` / `logger.debug`:

```python
self.logger.info(
    "%s: actor '%s' already participant in case '%s' — skipping (idempotent)",
    self.name, self.invitee_id, self.case_id,
)
return Status.FAILURE
```

**Distinction table**:

| Pattern | Ledger entry? | Disposition | Use case |
|---|---|---|---|
| Emit-side correlation marker | ✅ yes | `"rejected"` | Dedup guard for outbound activities |
| Received-side canonical entry | ✅ yes | `"recorded"` | CaseActor accepts a protocol assertion |
| Idempotency guard no-op | ❌ **no** | — | Already-processed duplicate detected |

**Resolved** (issue #2010, PR #2024): `SilentIdempotencyGuardMixin`
(`vultron/core/behaviors/idempotency.py`) now exists and satisfies CLP-13-002.
Implement all idempotency guards using this mixin.

---

## VFD/PXA Write-Boundary Validation in `CreateParticipantStatusNode`

(ISSUE-1825, 2026-07-30; ISSUE-2478, 2026-08-22; see also
`notes/case-state-model.md`)

`CreateParticipantStatusNode` validates VFD and PXA transitions inline at the
write boundary before any `dl.create()` / `dl.save()` call:

- `_check_vfd_preconditions()` calls `is_valid_vfd_transition(current, target)`
  and enforces role preconditions (CVDRole.VENDOR for `VFd`, CVDRole.DEPLOYER
  for `VFD`). Invalid jumps return `Status.FAILURE` (CSB-16-001,
  CSB-15-001/002).
- `_check_pxa_precondition()` calls `is_valid_pxa_transition(current, target)`.
  Invalid backward moves return `Status.FAILURE` (CSB-16-002).

**Defence layers as of PR #2503:**

- **Write node** (`CreateParticipantStatusNode`): fail-closed inline validation
  for VFD adjacency, VFD role preconditions, and PXA monotonicity (primary
  boundary).
- **Trigger path** (`add_participant_status_trigger_bt`): upstream
  `ValidateTriggerTransitionsNode` raises `VultronValidationError` before the
  BT write node is reached.
- **Received wire path** (`add_participant_status_tree`): uses the weaker
  `is_monotonic_vfd_forward` check intentionally — remote peers may advance
  through multiple VFD steps between status messages; strict adjacency applies
  only to local write nodes (CSB-16-001, AC-3).
- **Architecture ratchet** (`test/architecture/test_vfd_rm_pxa_write_sites.py`):
  AST-audits every `VfdDimension`/`RmDimension`/`PxaDimension` constructor
  call in `vultron/core/behaviors/`.

When writing or reviewing guard nodes that precede `CreateParticipantStatusNode`:
the write node is a second line of defence, but upstream guards still matter —
they surface invalid requests with richer error context before the BT write node
is reached.

<!-- Source: ISSUE-1825; GitHub concern #1896; PR #2307; ISSUE-2478; PR #2503 -->
