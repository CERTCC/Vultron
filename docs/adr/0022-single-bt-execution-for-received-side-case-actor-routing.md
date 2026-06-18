---
status: accepted
date: 2026-06-18
deciders: Vultron maintainers
consulted: >-
  notes/bt-integration.md, notes/case-communication-model.md,
  notes/case-ledger-authority.md, specs/case-ledger-processing.yaml,
  docs/adr/0021-caseactor-inbox-routing-canonical-ledger.md
---

# Single BT Execution Per Inbox Delivery for Received-Side CaseActor Routing

## Context and Problem Statement

ADR-0021 established that the CaseActor's own inbox delivery is the sole
path to a canonical ledger commit, and introduced a pre-flight guard
(CLP-10-002, CLP-10-003): a received-side use case compares
`receiving_actor_id` to the resolved `case_actor_id` in Python *before*
deciding whether to execute the guarded-commit BT
(`create_guarded_commit_case_ledger_entry_tree`).

Issue #1036 found that implementing that guard produced a second
anti-pattern: every adopting use case now runs **two separate**
`BTBridge.execute_with_setup()` calls per inbox delivery — one for the
use case's main operation (often under the message's own actor identity,
e.g. the invitee or accepting actor), and a second, conditionally
dispatched call for the guarded commit (under `receiving_actor_id`). The
condition that decides whether the second call happens at all is plain
Python control flow (`if receiving_actor_id != case_actor_id: return`),
not a node inside either tree.

An audit (issue #1036, broadened during planning) found this exact shape
in **9 use cases across 6 modules**:

- `vultron/core/use_cases/received/embargo.py`:
  `RemoveEmbargoEventFromCaseReceivedUseCase`,
  `InviteToEmbargoOnCaseReceivedUseCase`,
  `AcceptInviteToEmbargoOnCaseReceivedUseCase`
- `vultron/core/use_cases/received/report.py`:
  `ValidateReportReceivedUseCase`, `AckReportReceivedUseCase`
- `vultron/core/use_cases/received/note.py`: `AddNoteToCaseReceivedUseCase`
- `vultron/core/use_cases/received/status.py`:
  `AddParticipantStatusReceivedUseCase`
- `vultron/core/use_cases/received/case/lifecycle.py`:
  `CloseCaseReceivedUseCase`
- `vultron/core/use_cases/received/actor/case_manager_role.py`:
  `OfferCaseManagerRoleReceivedUseCase`

Every one of these imports and calls
`create_guarded_commit_case_ledger_entry_tree` directly from its own
`execute()` method, as a second, independently-gated tree execution. The
last one is structurally similar but slightly worse: its "main operation"
is plain procedural code (idempotent create + trigger-activity call), not
a BT at all — a separate, pre-existing BT-06-001 gap that the
implementation issue for this module should note but is not required to
fix as part of CLP-10-005.

This is the same class of problem the "Post-BT Procedural Cascade
Anti-Pattern" (`notes/bt-integration.md`) already names for the
validate→prioritize cascade: a cascade that is a *child* of the
triggering operation in the canonical model must be expressed as a BT
subtree, not as a procedural call (or a second, conditionally-dispatched
tree execution) sitting outside the tree in `execute()`. The fact that
the second tree's own internal guard (`CheckIsCaseManagerNode`) is
correctly role-gated does not fix the problem: the decision of *whether
to even ask the question* is still made in Python, once per inbox
delivery, instead of being one branch of one BT run.

A related architectural question raised during planning — whether the
inbox dispatch pipeline itself needs to be restructured so a use case
never has to ask "which actor am I running as" — turned out not to apply.
Investigation found `receiving_actor_id` is already resolved before
dispatch (`FastAPIDispatchAdapter.dispatch()`, which sets it from the
canonical actor ID resolved off the inbox URL path) and is already
present on every received-side event by the time `execute()` runs. The
dispatcher (`vultron/core/dispatcher.py`) has no CaseActor awareness and
needs none — it is a pure routing-table lookup keyed on
`semantic_type`. The gap is entirely at the use-case/BT boundary, not the
dispatch layer; no change to ADR-0020's proposed `process_payload` seam
is required by this decision.

## Decision Drivers

- The BT is the domain documentation (`specs/behavior-tree-integration.yaml`
  BT-06-001); a cascade that is invisible outside the tree structure is
  invisible to analysis and audit, regardless of whether the gating logic
  is "correct" in isolation.
- CLP-09-001 already requires the commit to be reached only through a
  role-gated *composition* — a Selector/Sequence/Success idiom evaluated
  inside the tree. A second, externally-gated `execute_with_setup()` call
  is not that composition; it duplicates the gate in a second place
  (Python) on top of the one already inside the guarded-commit tree.
- `receiving_actor_id` is already known before any use case runs (see
  Context). There is no remaining technical reason for a received-side
  use case to execute more than one BT per inbox delivery under more than
  one actor identity.
- Per-message asserter identities that differ from `receiving_actor_id`
  (e.g. `invitee_id`, `accepting_actor_id`) are legitimate inputs to leaf
  nodes — they are not legitimate values for the `actor_id` argument of
  `execute_with_setup()`, which must always be the identity of the
  DataLayer actually in scope for this invocation.

## Considered Options

**Option A — Single BT execution per inbox delivery; CASE_MANAGER gating
is an in-tree branch of the same tree (this ADR's decision).**
Each received-side use case calls `BTBridge.execute_with_setup()` exactly
once, with `actor_id=receiving_actor_id`. The use case's tree-factory
function composes the main operation subtree and the guarded-commit
subtree (`create_guarded_commit_case_ledger_entry_tree`, or an equivalent
Selector/Sequence/Success branch) as siblings or a sequence within one
tree. Any identity referenced by the message other than
`receiving_actor_id` (invitee, accepting actor, sender) is threaded into
the tree as leaf-node constructor arguments or blackboard keys — data,
not a second `actor_id`.

**Option B — Keep the current two-call shape; tighten only the
pre-flight guard's correctness (status quo, amended).**
Leave each use case's `execute()` performing two `execute_with_setup()`
calls, but ensure the second call's `actor_id` is always provably
`receiving_actor_id` (already true after ADR-0021/CLP-10-003). This
satisfies CLP-10-002/CLP-10-003 literally but leaves the underlying
cascade-visibility problem unresolved: the decision to run the commit
step at all is still Python control flow outside any tree.

**Option C — Move the pre-flight guard into a wrapper BT that always
runs, with the use case's main tree as a child.**
Introduce a top-level "received-side dispatch tree" per use case that
always executes under `receiving_actor_id`, with the existing main tree
and the guarded-commit tree as two children, but keep them as
independent tree objects rather than fully merging composition. This is
a smaller diff than Option A in the short term but reintroduces a
two-tree-construction split that makes it easy to drift back into the
Option B shape during future edits, since the "merge point" is itself
external to either tree's own factory function.

## Decision Outcome

Chosen option: **Option A — single BT execution per inbox delivery, with
CASE_MANAGER gating as an in-tree branch of the same tree**.

```text
ReceivedUseCase.execute()
  └── ONE call: bridge.execute_with_setup(tree, actor_id=receiving_actor_id)

tree = create_<use_case>_received_tree(...)   # single factory function
  ├── <main operation subtree>                 # may reference invitee_id /
  │                                             # accepting_actor_id etc. as
  │                                             # leaf-node data, never as a
  │                                             # second actor_id
  └── Selector("GuardedCommitOrSkip")
        ├── Sequence
        │     ├── CheckIsCaseManagerNode(case_id=case_id)
        │     └── CommitCaseLedgerEntryNode(case_id=case_id)
        └── Success("CommitSkippedNotCaseManager")
```

`CheckIsCaseManagerNode` resolves the case's `CVDRole.CASE_MANAGER`
participant and compares it against the actor active for *this*
invocation (`receiving_actor_id`, since that is now always the BT's
`actor_id`) — the same role check already required by CLP-09-001, now
reached through exactly one tree execution instead of two.

This amends ADR-0021's CLP-10-002/CLP-10-003 call-shape (which it leaves
intact at the routing level — the CaseActor's own inbox delivery is still
the only path to a commit) by replacing the *external* pre-flight guard
with an *internal* one. CLP-10-001 (every protocol-significant trigger
tree emits to `case_manager_id`) is unaffected.

### New Normative Requirement

`specs/case-ledger-processing.yaml` gains CLP-10-005: a received-side use
case MUST NOT import or call
`create_guarded_commit_case_ledger_entry_tree` (or any other guarded-commit
factory) directly from `vultron/core/use_cases/`; it MUST be composed as a
child of the use case's own tree-factory function in
`vultron/core/behaviors/`, reached through the single
`execute_with_setup()` call already used for the use case's main
operation. A structural test enumerates known violations as a ratchet
(`test/architecture/test_single_bt_execution_received_side.py`).

### Consequences

- Good, because the cascade from "process this message" to "commit a
  canonical entry if I'm the CaseActor" becomes visible in tree structure,
  consistent with every other cascade in the codebase (BT-06-001/006).
- Good, because it eliminates a structurally duplicated gate (Python
  check + in-tree `CheckIsCaseManagerNode`) in favor of one gate, in one
  place, evaluated once.
- Good, because the fix requires no change to the inbox dispatch pipeline
  or ADR-0020's proposed seam — `receiving_actor_id` is already available
  before any use case executes.
- Neutral, because use cases whose main operation legitimately needs a
  different actor identity for some leaf nodes (e.g. the Invite/Accept
  embargo handshake, where `UpdateParticipantEmbargoPecNode` /
  `RecordParticipantAcceptanceNode` need `invitee_id`/`accepting_actor_id`)
  must thread that identity through as leaf-node data rather than as
  `execute_with_setup`'s `actor_id` — a real design change to those trees,
  not just a call-site edit.
- Bad, because all 9 known call sites require a tree-factory redesign
  (not a one-line fix), and discovering the same shape required a
  full-codebase audit rather than fixing the 3 sites originally named in
  issue #1036 — the true scope was about 3x the originally reported
  evidence.

## Validation

- `specs/case-ledger-processing.yaml` CLP-10-005 codifies the requirement
  from this ADR.
- `test/architecture/test_single_bt_execution_received_side.py` enumerates
  the 6 known-violating modules (9 use cases) as a ratchet set (mirroring
  `test/architecture/test_core_no_adapter_imports.py`): the test fails if
  a new violation appears, and fails if a known violation is fixed but not
  removed from the set — forcing each migration to update the test.

## More Information

- Issue #1036 — concern that identified the anti-pattern (3 originally
  cited call sites) and the planning session that broadened the audit to
  8.
- Issue #1038 — folded into this ADR's implementation graph; it had
  independently proposed the same single-BT shape for the Invite/Accept
  embargo pair and is superseded by the implementation issue covering
  `embargo.py`.
- ADR-0021 — establishes the CaseActor-inbox-is-sole-commit-path routing
  rule this ADR's call-shape change builds on; not superseded, only
  amended at the call-shape level.
- `notes/bt-integration.md` § "Guarded Commit: Role-Gated Canonical
  Writes" — the existing Selector/Sequence/Success idiom this decision
  requires to be reached through a single tree execution.
- `notes/case-communication-model.md` § "Known Implementation Gaps" —
  tracks the per-module migration status.
