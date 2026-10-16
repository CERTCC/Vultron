---
title: Behavior Tree Integration Design Notes
status: active
kind: guidance
tags: [bt, behavior-trees, py_trees, blackboard, BT-nodes, protocol-cascades]
description: >
  Rules for integrating py_trees behavior trees with use cases: the design
  decisions that bind new trees, actor and identity isolation, the BT
  concurrency lock, why all protocol-significant behavior lives in the tree,
  why a delivery's trees are composed and never chained, the received-side
  stages, and how to translate a simulator tree.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/handler-protocol.yaml
  - specs/inbox-endpoint.yaml
  - specs/case-ledger-processing.yaml
  - specs/embargo-policy.yaml
  - specs/participant-case-replica.yaml
  - specs/case-bootstrap-trust.yaml
  - specs/case-management.yaml
  - specs/case-proposal.yaml
  - specs/sync-ledger-replication.yaml
  - specs/vultron-as2-mapping.yaml
related_notes:
  - notes/bt-canonical-reference.md
  - notes/call-out-configuration.md
  - notes/bt-composability.md
  - notes/case-ledger-authority.md
  - notes/bt-pitfalls.md
  - notes/embargo-lifecycle.md
  - notes/protocol-event-cascades.md
  - notes/use-case-behavior-trees.md
  - notes/testing-pitfalls.md
  - notes/inbox-orchestration.md
  - notes/participant-embargo-consent.md
  - notes/case-proposal.md
  - notes/bt-design-patterns.md
  - notes/coordination-agents.md
  - notes/event-driven-control-flow.md
  - notes/received-status-authorization.md
  - notes/triggerable-behaviors.md
  - notes/flaky-tests.md
  - notes/activitystreams-semantics.md
  - notes/activitystreams-state-update.md
  - notes/codebase-structure.md
  - notes/documentation-strategy.md
  - notes/domain-validation.md
  - notes/protocol-asks.md
  - notes/structured-logging.md
  - notes/ownership-transfer-close-paths.md
relevant_packages:
  - py_trees
  - vultron/bt
  - vultron/core/behaviors
  - vultron/core/use_cases
---

# Behavior Tree Integration Design Notes

Use cases in `vultron/core/use_cases/` run `py_trees` behavior trees through
the bridge in `vultron/core/behaviors/`. All protocol-significant behavior MUST
be BT nodes or subtrees (BT-06-001).

**Key boundary**: `vultron/bt/` is the simulation BT engine (custom; do NOT
modify it or reuse it in prototype handlers). `vultron/core/behaviors/` uses
`py_trees`. The two coexist and MUST NOT be merged (ADR-0008).

---

## Design Rules for New Trees

- **Handler-first** (ADR-0007): use cases call BTs; a BT never consumes
  ActivityStreams directly or replaces semantic extraction and dispatch.
- **DataLayer is the state store**: persistent state lives in the DataLayer;
  the py_trees blackboard holds transient in-execution state only.
- **Blackboard keys contain no slashes** (py_trees parses them as paths). Use
  `{noun}_{id_segment}`, where `id_segment` is the last path segment of the
  object's URI: `object_abc123`, `case_def456`, `actor_vendorco`.
- **One focused tree per workflow**: each BT-backed `MessageSemantics` has its
  own tree; compose larger workflows from subtrees
  (`notes/bt-composability.md`), never one monolithic protocol tree.
- **Single-shot execution**: a tree runs to completion per invocation and keeps
  no state between invocations; one execution commits its act's ledger entry,
  then one entry per further change to the case file (CLP-07-013).
- **Case authority is a role, not a per-case object** (CP-08-002/003). The
  CASE_MANAGER role is held by one actor per container with the stable identity
  `{case_actor_service_url}/actors/case-actor`. Never compute a per-case
  identity such as `.../actors/case-actor-{slug}`: nobody hosts it, so delivery
  404s. `case_actor_identity()` (`case/case_actor_identity.py`) derives the
  configured identity; `EnsureCaseActorHostedNode` provisions the record locally
  and returns `SUCCESS` when the actor is hosted elsewhere
  (`case/nodes/case_setup.py`).
- **CLI invocation** of individual BTs is supported for testing and agents
  (BT-08).

---

## Actor Isolation and BT Domains

Each actor has its own BT execution domain and blackboard. Actors interact
ONLY through ActivityStreams messages, and each actor's RM/EM/CS state is
private.

### The store follows the executing actor (BT-05-005)

Under per-actor storage the blackboard `actor_id` determines which store the
tree operates on, so `BTBridge` **reconciles** the injected store to the
executing actor (`BTBridge._store_for_actor` →
`vultron/core/behaviors/store_scope.py::store_for_actor`) instead of trusting
the caller. Divergence bites on delegated emits: a trigger emitting on the
CASE_MANAGER's behalf with the requester's DataLayer would create the activity
in one store and queue it in the other's outbox, so it is never delivered.

A store that reports no `actor_id` (a test double) is passed through untouched,
and a test may let the identities differ deliberately to assert the skip path.

### Role-gated trees: three identities must be one (BT-05-006)

Where a tree is gated on a role held in the case, the **role holder**, the
**receiving actor** and the **store owner** must be one actor. If any two
drift, the gate evaluates against an actor holding no role and returns
SUCCESS-by-skip with nothing written.

Gate on the role (`create_case_manager_gated_tree`), never by comparing
`actor_id` against a computed `case_actor_id` (CM-24-004). Once the emit is
role-gated, the executing actor *is* the case manager, so the activity and its
outbox entry land in one store by construction.

### The message subject is a fourth identity, and it must stay separate

The *subject* a message names (invitee, accepting, rejecting or target actor)
answers "whose consent/state is this about?". That is neither "whose replica am
I applying it to?" (`resolve_receiving_actor_id()`) nor "who is executing the
tree?" (blackboard `actor_id`).

Read subject identities **from the message** and thread them into the tree as
leaf-node constructor data, never derived from the receiving actor (ADR-0022).
They coincide with the receiving actor on direct delivery, so a conflation
passes tests and breaks only under CLI dispatch, log replay, CASE_MANAGER relay,
or a multi-recipient activity (ISSUE-2762). Watch for:

- **Reusing the resolved receiving actor as a subject.**
- **A tree factory that accepts a subject argument and only logs it**, behind a
  lookup that falls back to the execution actor when the subject is falsy. Log
  at WARNING when a named subject did not resolve, as
  `CanAnswerEmbargoInviteNode` does.

For an `Invite(EmbargoEvent)` the invitee is the Invite's *sole* `to:`
recipient (EP-09-010, ADR-0113). `resolve_invitee_id()`
(`vultron/core/use_cases/received/embargo/invite.py`) returns it in canonical
spelling and raises `VultronProtocolViolationError` naming the recipient count
otherwise, which the use case reports as `REFUSED`. A proposal addressed to the
CASE_MANAGER names the manager as sole recipient, but the manager adjudicates it
and is never its invitee, so its own record gets no RSVP deadline (CM-28-003).

Where a message legitimately names several recipients (the report `Offer`),
test membership with `is_addressed_to()` (`vultron/core/predicates/addressing.py`),
never a bare `in`: `to:`/`cc:` arrive as the sender wrote them, so a trailing
slash misses an exact match (#2667). Full rule: `vultron/core/AGENTS.md`
§ "A Message Subject Is Never `resolve_receiving_actor_id()`".

---

## Concurrency Model

Messages are processed sequentially per actor: the inbox endpoint returns 202
and queues work on `BackgroundTasks`. BT execution runs on a **thread pool**,
never on the event loop:

- Trigger routes are synchronous `def` endpoints, so Starlette runs them via
  `anyio.to_thread.run_sync`.
- The inbox background task (`run_inbox_pipeline`) is `async def` and so runs
  on the event loop; it hands the synchronous BT pipeline (`process_payload`
  and the replay loop) to `asyncio.to_thread` itself, inside the per-actor
  asyncio lock (IE-06-003). Without that hop every inbound activity stalls the
  whole container for its BT tick (#3033).

Two BT executions therefore run on different threads at once, and
`py_trees.blackboard.Blackboard.storage` is process-global and not thread-safe.
`BTBridge.execute_with_setup` wraps setup → execute → cleanup in a module-level
`threading.RLock`; it must be an `RLock` because `lifecycle.py` nodes call
`execute_with_setup` recursively. Without it one thread's `actor_id` overwrites
another's and an outbound activity lands in the wrong actor's outbox (PR-886).

---

## All Protocol-Significant Behavior MUST Be in the BT

There is no "simple enough to skip" threshold. Emitting activities,
transitioning RM/EM/CS state, creating or updating protocol-state objects, and
cascading to downstream behaviors (validate → engage/defer) are all BT nodes or
subtrees (BT-06-001, BT-06-005, BT-06-006). A behavior outside the tree is
invisible to analysis, audit, and explainability.

**Post-BT procedural cascade anti-pattern**: calling another use case from
`execute()` after the tree succeeds (`if bt.status == SUCCESS:
SvcEngageCaseUseCase(...).execute()`) hides the cascade. Express it as a child
subtree of the tree instead (`create_prioritize_subtree` in
`report/prioritize_tree.py` is the reusable engage/defer subtree).

### Procedural Glue Exception

`execute()` MAY contain infrastructure glue only: instantiate the BT, set up the
blackboard from the event, call `bridge.execute_with_setup()`, check the
status, extract output from the blackboard.

A call from `execute()` to a helper that writes to the DataLayer is **not**
glue, whatever the helper is named (CLP-10-020, ADR-0111). The ratchet
`test/architecture/test_no_dl_mutations_in_execute.py` resolves calls from a
received `execute()` transitively through anything defined under
`vultron/core/use_cases/` (module helper, `self._method()`, relative or
re-exported import, any depth), stopping at the package boundary, so a BT node's
write is never a violation. Its `KNOWN_VIOLATIONS` set is empty; a new entry
needs the issue that owns its removal. Trigger-side bodies get only the direct
rule (BT-15-001).

### Compose Trees, Never Chain Them (ADR-0135)

A received delivery runs **one** tree (CLP-10-005). If the work needs two trees,
write the tree that composes them: the door check, the expiry, the refusal and
the alternative branch are nodes, guards, `refusal_effects` and selectors inside
it, built by its factory. Python in a use case never chooses between trees or
runs one after another — not in `execute()`, and not in a helper it calls, which
counts as `execute()` (resolved transitively, as CLP-10-020 does for writes).
Reason: a step outside the tree is invisible to the ratchets and to a reader;
ADR-0022 rejected the Python-chosen cascade, and helpers had moved it one call
down (#4585). A one-node tree run by a helper "before the tree" is that
cascade: add the node to the tree instead.

Two shapes look like a second tree and are not:

- **A CASE_MANAGER clock decision** (an expiry) is a stage of the one tree,
  between the door guards and the precondition guards (CLP-10-025).
- **A drained gap-buffer entry** is another delivery: hand it back to the
  receiving actor's inbox, never run its tree inline or from a node — a bridge
  run nested in a node hides the inner tree's internal error (SYNC-14-009).

### The Received-Side Stages (ADR-0111, ADR-0135)

A received-side tree composed via `create_receive_activity_tree`
(`vultron/core/behaviors/case/receive_activity_tree.py`) runs its stages in a
fixed order (CLP-10-006, CLP-10-010): intake, door guards, clock decisions,
guards, commit, effects.

1. **Intake** — `IntakeReceivedActivityNode` (`case/nodes/intake.py`) archives
   the received activity exactly as received, idempotently, as a
   `ReceivedActivityRecord` whose id the *receiver* derives
   (`build_id(sender_activity_id)`), carrying the sender's id for reverse
   lookup. Never store under the sender's id: one id-keyed table per actor lets
   a sender squat an id we derive for our own records. Readers of the archive go
   through `build_id`. Intake decides nothing, ledgers nothing, and writes
   nothing else (CLP-10-017); it runs first so a refusal still leaves the
   archive (CLP-10-018). An object carried inline (case, note, status, embargo)
   is a message shaped like that object; the record core keeps is written by an
   effect node after the guards, because a stored case row *is* the replica
   (PCR-03-004, CBT-01-005).
2. **Door guards** — in order: the post-close write boundary (CM-23-013), the
   addressee check (HP-01-005) and the sender guard (HP-01-006).

   Directly after intake the factory places `CaseOpenToExternalWritesNode`
   (`case/nodes/post_close.py`), the CM-23-013 write boundary: at the case's
   CASE_MANAGER, once the ledger holds `case_fully_closed`, it fails the tree so
   no commit, effect, or emit runs; on every other store it passes, so replicas
   keep applying the closure fan-out. The handler verdict comes from
   `post_close_refusal` (`use_cases/received/_bt_verdict.py`), asked first by
   `verdict_from_bt` and `applied_or_raise`, so it is `REFUSED`. The one-node
   pre-tree runs in `_sender_preflight.py` (`door_refusal`, which runs
   `post_close_refusal_before_tree`, `unaddressed_copy_refusal` and
   `rule_refusal` in that order, and `repeat_answer_skip`) are the chained
   shape CLP-10-005
   forbids; compose their guard into the tree, never add a caller. A tree
   opts out only with a `PostCloseExemption`. `post_close_reply` takes emit-only
   nodes that answer the refusal; only the close-case tree passes one
   (`Reject(Leave)` under `ActorConfig.post_close_reply = reject`). Every other
   late activity is dropped with no reply (ADR-0131, CM-23-017). The addressee
   check and the sender guard follow.
3. **Clock decisions** — a decision the CASE_MANAGER takes from its own clock
   or policy before judging the activity: an expiry, or the embargo end-time
   check (CLP-10-025). It runs after the door guards, so an unentitled sender
   never makes it write, and before the guards, because it is ledgered even
   when the activity is then admitted (a new ownership Offer after the open one
   expired, CM-21-014). It runs only at the CASE_MANAGER, commits only its own
   entries — one per AS2 activity it needs, never the received activity's —
   and reads only the clock, policy and the case's ledger and file. The
   end-time check is about the case, so the factory adds it to every tree with
   a case and both door guards (`case_clock_decisions`), and a case-scoped
   trigger runs the same gated stage first in its own tree (BT-15-003). A
   commit the ledger refuses logs a warning and does not end the tree; an
   internal error does. A decision built from CASE_MANAGER commit nodes, which
   raise on a failed commit, must judge the ledger's refusal (a gapped prefix,
   SYNC-10-001) as FAILURE before it commits, as `end_time_clock_decision`
   does with `CheckLedgerFreshnessNode`. Pass
   the decision as `clock_decisions`: the factory wraps each in a
   `ClockDecision` inside a `ClockDecisionStage`
   (`case/nodes/clock_decision_stage.py`) behind a CASE_MANAGER gate, and
   refuses one that holds the received activity's commit, or a tree with no
   `sender_rule` or with a `post_close_exemption`, where a door guard would
   not run before the decision writes (HP-01-006, CM-23-013). The ownership
   Offer expiry (`ExpireOverdueOwnershipOfferNode`,
   [ownership-transfer-close-paths](ownership-transfer-close-paths.md)) and
   the embargo Invite expiry (`invite_expiry_decision`) are clock decisions,
   as is the overdue-invitation sweep (`embargo_clock_decisions`, CM-28-015),
   which every received embargo tree passes and `SvcEmbargoTriggerBase` adds
   to its triggers' stage; never run one as a tree of its own before the
   received tree.
4. **Guards** — read-only precondition checks that return FAILURE to refuse and
   write nothing. A refusal goes to the process log and, where the protocol
   calls for an answer, back to the sender — never to the ledger (CLP-05-002).
   A tree that owes that answer passes it as `refusal_effects` (CLP-10-022): the
   factory wraps the guards in a `PreconditionGuardStage`
   (`case/nodes/refusal_stage.py`) that runs them only when a precondition guard
   (not the sender guard) fails, inside a CASE_MANAGER gate, and skips them on a
   redelivery whose intake was already archived. The stage then fails with the
   guard's reason, so nothing commits and the handler reads `REFUSED`. A refusal
   effect must be `EmitCapable` and hold no `StateWriteCapable` node. Do not
   hand-build a `Selector[guard, emit]`: the emit would run ahead of the commit
   on an accepted delivery.
5. **Commit** — the CASE_MANAGER ledgers the received activity as received, a
   postmark on the envelope (ADR-0107, CLP-07-011); it never rebuilds the
   assertion from processed state. Every commit goes through
   `CommitCaseLedgerEntryNode`; a received `execute()` never commits (BT-06-006).
6. **Effects** — apply the accepted assertion to the local replica and enqueue
   cascades. `replica_effects` run on every replica; `manager_effects` run only
   at the CASE_MANAGER, inside the gate the factory adds (BT-17-008; see
   `notes/bt-pitfalls.md` § "A Received Tree Gets Its CASE_MANAGER Gate From
   the Factory").

**Intake is the only path that stores the received activity** (CLP-10-019). Do
not add a per-tree store node or handler-local store helper. A receive tree
that does not compose through the factory runs no intake; the exceptions are an
exact set, `KNOWN_FACTORIES_BYPASSING_INTAKE`, in
`test/architecture/test_receive_side_intake_first.py`, each with its reason. The
ratchet also checks that the factory *returns* the shared factory's result
(`KNOWN_FACTORIES_NESTING_INTAKE`, empty): nesting it under a hand-built root
runs something before intake. A tree that needs a branch ahead of the receipt
commit uses an outer factory with `case_id=None` (intake, no commit) and an
inner factory per arm that commits; the inner intake finds the archive and
writes nothing. Intake archives nothing when the event carries no activity, so
a semantic-registry entry must set `include_activity=True`. A handler that
turns a delivery away before it can build its tree uses `refuse_after_intake`
(`use_cases/received/_intake_only.py`).

**The factory commits only when given a `case_id`**, and CLP-10-013 requires a
commit exactly when the received `(type, object)` pair is a canonical payload
signature (`_CANONICAL_PAYLOAD_SIGNATURES`); otherwise the CASE_MANAGER would
refuse its own commit. The `Announce(VulnerabilityCase)` tree passes
`case_id=None` by decision: only the CASE_MANAGER sends it and only replicas
receive it, so the gate could only skip. `Update(VulnerabilityCase)` has no
received tree; an inbound one resolves to `UNKNOWN` and is refused (#4443).
Nor do `Create(CaseStatus)`, `Create(ParticipantStatus)`, `Create(Event)` or a
direct `Create(CaseParticipant)`: storing the record they carry would change
the case file with no entry (CLP-07-013), and the protocol does not allow them:
each record enters a case only by its one attaching message (VAM-01-011,
ADR-0137).
Every other tree whose activity is canonical passes `case_id`, with its
refusing nodes in `precondition_guards`, so a refused activity leaves no entry.

### Trigger/Received Parity

The BTBridge requirement applies equally to trigger-side `execute()` methods.
RM transitions, `EmbargoLifecycle` calls, and `ParticipantStatus` writes with a
specific `rm_state` are protocol-significant (BT-15-001, BT-06-006): they live in
BT leaf nodes run via `bridge.execute_with_setup()`, never inline in
`execute()`. On a non-`SUCCESS` status the trigger raises with
`BTBridge.get_failure_reason(tree)`.

---

## Simulation-to-Prototype Translation Strategy

Use the simulation trees in `vultron/bt/` as **architectural reference**, not
code to reuse; the custom engine's initialization is incompatible with
py_trees.

1. Find the simulation tree in `vultron/bt/report_management/_behaviors/` (or
   the embargo/case equivalents).
2. Keep its sequence/fallback composition and node ordering.
3. Map condition nodes (e.g. `RMinStateValid`) to `Behaviour` subclasses that
   check DataLayer state.
4. Replace fuzzer nodes with call-out points (`notes/call-out-configuration.md`);
   the fuzzer catalog is `docs/developer/reference/bt-fuzzer/index.md`.
5. Preserve state-transition order and precondition checks; wrap state changes
   in DataLayer updates; emit ActivityStreams activities to the outbox where the
   simulation emits messages.

`vultron/bt/case_state/` has only `conditions.py` and `transitions.py` (no
`_behaviors/`): build case nodes from the ActivityPub how-to docs, using those
as state-machine reference. In `vultron/bt/embargo_management/`, `Accept` is an
**activity type** that triggers `PROPOSED → ACTIVE` (or `REVISE → ACTIVE`), not
a state; `states.py` is the authoritative state list.

**Source of truth priority** when the sources conflict:

1. `docs/howto/activitypub/activities/*.md` — process descriptions, message
   examples, workflow steps.
2. `vultron/bt/report_management/_behaviors/*.py` — state-machine logic, tree
   composition.
3. `docs/topics/behavior_logic/*.md` — conceptual diagrams, motivation.

### py_trees Fuzzer Node Home: `vultron/demo/fuzzer/`

py_trees re-implementations of `vultron/bt/` fuzzer nodes go in
**`vultron/demo/fuzzer/`**, never `vultron/core/behaviors/` (BT-16-004): they
are simulation stubs for call-out points, not protocol
behavior. Modules mirror the simulator: `base.py` (probabilistic base types),
`embargo.py`, `messaging.py`, and `report_management/`.
`vultron/bt/vul_discovery/fuzzer.py` is intentionally not ported: discovery
happens upstream of Vultron, which starts at `Offer(VulnerabilityReport)`.

Each fuzzer node's docstring names (BT-16-005):

1. its semantic function in the CVD process;
2. the external input it simulates — **system integration**, **human
   decision**, or **environmental check**;
3. its approximate success probability (the `WeightedBehavior` subclass);
4. its automation potential (High / Medium / Low / N/A).

---

## EvaluateCasePriority: Outgoing Direction Only

`EvaluateCasePriority` (`vultron/core/behaviors/report/nodes/conditions.py`) is
for the **outgoing direction**: the local actor deciding whether to engage or
defer a validated report. The receive-side `EngageCaseBT` and `DeferCaseBT`
(`report/prioritize_tree.py`) do not use it; they record the **sender's
already-made decision** in the sender's
`CaseParticipant.participant_status[].rm_state`. Activities are state-change
notifications, not commands, so a received `Join`/`Ignore(VulnerabilityCase)`
needs no policy evaluation.

## RM Is Participant-Specific

Each `CaseParticipant` carries its own RM state in
`participant_status[].rm_state`. Handlers such as engage/defer update
participant-level RM state; there is no case-level or flat report RM status. The
CASE_MANAGER creates the case and its participants from the report receiver's
`Create(as_CaseProposal)` (ADR-0041; `notes/case-proposal.md`).

---

## Related

- `notes/bt-canonical-reference.md` — canonical CVD protocol BT subtree map,
  node symbol legend, BT-IDM anti-patterns
- `notes/bt-composability.md` — composing trees from subtrees
- `notes/bt-pitfalls.md` — per-pitfall notes on blackboard semantics,
  idempotency, role guards
- `notes/use-case-behavior-trees.md` — tree-is-the-documentation and no
  post-tree cascades
- `notes/protocol-event-cascades.md` — cascade gaps and BT subtree fixes
- `notes/vultron-bt.txt` — full canonical CVD protocol BT dump (read-only)
