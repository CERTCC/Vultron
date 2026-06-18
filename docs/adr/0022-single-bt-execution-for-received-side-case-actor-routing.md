---
status: accepted
date: 2026-06-18
deciders: Vultron maintainers
consulted: >-
  notes/bt-integration.md, notes/case-communication-model.md,
  notes/case-ledger-authority.md, specs/case-ledger-processing.yaml,
  docs/adr/0021-caseactor-inbox-routing-canonical-ledger.md,
  issue #1047
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

An audit (issue #1036, broadened during planning to also resolve a
follow-on Concern, issue #1047, which independently named the same
anti-pattern in `status.py` and asked for it to be codified as a
spec-level invariant) found the underlying violation in **9 use cases
across 6 modules**, but
not all in the same precise shape. There are three distinct ways the
"execute() does nothing but build one tree, run it once, handle the
result" intent was violated:

**(1) Genuine actor-identity switching** — a real second
`execute_with_setup()` call under a different actor than the main
operation's. This is the literal anti-pattern #1036 and #1047 describe:

- `vultron/core/use_cases/received/embargo.py`:
  `RemoveEmbargoEventFromCaseReceivedUseCase`,
  `InviteToEmbargoOnCaseReceivedUseCase`,
  `AcceptInviteToEmbargoOnCaseReceivedUseCase` — main tree runs under
  `request.actor_id` / `invitee_id` / `accepting_actor_id`; a second,
  separately constructed `create_guarded_commit_case_ledger_entry_tree`
  runs under `receiving_actor_id`. **Notably, the main tree (built by
  `vultron/core/behaviors/embargo/announce_teardown_tree.py`'s factory
  functions) already composes the identical guarded-commit branch as its
  own last child** — but because the main tree executes under the
  invitee's/accepting actor's identity, `CheckIsCaseManagerNode` inside it
  is a guaranteed no-op (that actor is essentially never the CaseActor).
  The second, separately-dispatched call is the one that actually fires,
  on the rare second attempt under the correct identity. The fix is not
  "add a guarded-commit branch" (it already exists) — it is "stop calling
  the tree under the wrong actor a second time, and run the one tree that
  already has the branch under `receiving_actor_id` instead."
- `vultron/core/use_cases/received/report.py`:
  `ValidateReportReceivedUseCase` (main operation is a separate
  `ValidateCaseUseCase` call under `actor_id`, not even a tree of its own),
  `AckReportReceivedUseCase` (main tree under `request.actor_id`) — both
  followed by a second, separately-gated guarded-commit call under
  `receiving_actor_id`/`case_actor_id`.
- `vultron/core/use_cases/received/status.py`:
  `AddParticipantStatusToParticipantReceivedUseCase` — main tree
  (`add_participant_status_tree`) under `request.actor_id`, then a second
  guarded-commit call under `case_actor_id` via `_commit_log_cascade_bt()`.
  This is the exact site #1047 cited as its primary evidence.

**(2) Single BT call, but non-BT procedural code precedes it** — only one
`execute_with_setup()` call exists (the commit), but `execute()` still
does domain-significant work outside any tree before reaching it, so it
is not "build one tree, run it, handle the result" either:

- `vultron/core/use_cases/received/note.py`: `AddNoteToCaseReceivedUseCase`
  — appends to `case.notes`, calls `dl.save()`, and broadcasts to peers, all
  in plain Python, before the single guarded-commit `execute_with_setup()`
  call.
- `vultron/core/use_cases/received/actor/case_manager_role.py`:
  `OfferCaseManagerRoleReceivedUseCase` — idempotent-creates the activity
  and calls a trigger-activity port directly in Python, before the single
  guarded-commit call. This is a pre-existing BT-06-001 gap (the main
  operation was never expressed as a BT at all), not actor-switching.

**(3) Single BT call under the correct actor, but assembled ad hoc** —
no actor-switching and no procedural code outside the tree, but the tree
itself is built inline in `execute()` rather than via a
`vultron/core/behaviors/` factory function:

- `vultron/core/use_cases/received/case/lifecycle.py`:
  `CloseCaseReceivedUseCase` — constructs a one-off
  `py_trees.composites.Sequence` directly inside `execute()`, combining
  `StoreActivityNode` and the guarded-commit subtree, and runs it once
  under `receiving_actor_id`. This already satisfies the actor-identity
  requirement; the fix here is purely "move this tree into a named factory
  function in `behaviors/case/`," not an actor-switching repair.

All nine sites import `create_guarded_commit_case_ledger_entry_tree`
directly into `vultron/core/use_cases/`, which is what the structural test
(below) detects — but the underlying defect, and the fix required, differs
by category. This is the same class of problem the "Post-BT Procedural
Cascade Anti-Pattern" (`notes/bt-integration.md`) already names for the
validate→prioritize cascade: a cascade that is a *child* of the triggering
operation in the canonical model must be expressed as a BT subtree, not as
a procedural call (or a second, conditionally-dispatched tree execution,
or any other domain-significant code) sitting outside the tree in
`execute()`. The fact that the in-tree guard (`CheckIsCaseManagerNode`) is
itself correctly role-gated does not fix category (1): the decision of
*whether to even ask the question* is still made in Python, once per
inbox delivery, instead of being one branch of one BT run.

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
case's `execute()` method MUST do exactly three things — build one BT via
a `vultron/core/behaviors/` tree-factory function, call
`BTBridge.execute_with_setup()` exactly once under
`actor_id=receiving_actor_id`, and handle the result. No other
domain-significant code (a second BT execution, direct DataLayer
mutation, or a direct import of the guarded-commit factory) may appear in
`execute()`. A structural test enumerates known violations as a ratchet
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
- Bad, because the 9 known call sites need three different kinds of fix
  (genuine actor-switching repair for 6 of them; moving procedural code
  into a new BT for 2 of them; just relocating an already-correct inline
  tree into a factory function for 1 of them), so the implementation
  issues cannot treat all 9 as the same mechanical change — and
  discovering the full set required a full-codebase audit rather than
  fixing the 3 sites originally named in issue #1036, plus the 1
  additional site #1047 named independently.

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
  9.
- Issue #1047 — independent concern naming the same anti-pattern at
  `status.py` and requesting it be codified as a spec-level invariant;
  fully covered by this ADR and CLP-10-005, superseded.
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
