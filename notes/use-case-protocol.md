---
title: Use-Case Protocol — Results, Dispositions, and Request Paths
status: active
kind: guidance
description: >
  Rules for use-case results: which HandlerDisposition a received-side exit
  returns, how a verdict reaches InboxOutcome, why the two request paths stay
  separate, and the trigger-side route contract.
related_specs:
  - specs/use-case-organization.yaml
  - specs/handler-protocol.yaml
  - specs/case-ledger-processing.yaml
  - specs/inbox-orchestration.yaml
  - specs/triggerable-behaviors.yaml
related_notes:
  - notes/use-case-behavior-trees.md
  - notes/architecture-hexagonal.md
  - notes/inbox-orchestration.md
  - notes/case-communication-model.md
relevant_packages:
  - vultron/core/models
  - vultron/core/ports
  - vultron/core/use_cases
  - vultron/core/use_cases/received
  - vultron/core/use_cases/triggers
  - vultron/core/behaviors/inbox
---

# Use-Case Protocol — Results, Dispositions, and Request Paths

The result types live in `vultron/core/models/use_case_result.py`: received-side
use cases return `HandlerResult`, trigger-side ones their verb's `TriggerResult`
subtype. Requirements: UCORG-05. Decisions: ADR-0040 (result envelope, no
`UseCaseRequest`), ADR-0095 (received-side verdict), ADR-0110 (trigger dispatcher
over a verb registry).

---

## Assigning a disposition

`HandlerDisposition` maps onto `InboxOutcome.status` in `DispatchNode`:
`APPLIED` and `SKIPPED` → `processed`, `DEFERRED` → `deferred`, `REFUSED` →
`rejected` with `failure_reason`. Handlers never use `InboxOutcome` vocabulary
themselves (HP-01-004, `test_use_cases_no_inbox_outcome.py`).

Most handlers run a tree; `vultron/core/use_cases/received/_bt_verdict.py` turns
the run into a verdict. `verdict_from_bt` is the default reading: `SUCCESS` →
`APPLIED`, a leadership skip → `SKIPPED`, `internal_error` or a missing port →
raise `VultronBTInternalError`, any other `FAILURE` → `REFUSED` with the failing
leaf's reason. `applied_or_raise` is for a tree that only stores what the handler
already accepted, where any failure can only be the DataLayer's.

A handler refines the default by asking which node decided (`node_failed`,
`node_succeeded`, `find_node`, `find_named`), never by matching a node's
`feedback_message`, which usually embeds ids. Where later steps run only on
`APPLIED`, return early on anything else.

| Exit | Disposition |
|---|---|
| Internal or infrastructure failure, missing port | raise |
| Malformed activity (missing id, object or field) | `REFUSED` |
| Activity about a case this actor does not hold | `REFUSED` |
| Invalid transition; untrusted, non-participant or non-owner sender | `REFUSED` |
| The handler answered with a `Reject` or a decline | `REFUSED` |
| Not this actor's role (a CASE_MANAGER-addressed message at a non-manager, via `case_manager_verdict()`), or a copy whose `to` does not name it (`cc` addresses nobody, ADR-0109; a `cc`-only `Offer(Report)` is one, HP-10-001) | `REFUSED` (HP-01-005) |
| An addressee's first receipt of a message now pending its own decision (the Case Owner and `Offer(CaseParticipant)`), or of the CASE_MANAGER's direct removal or reinstatement notice, which its replica applies from the ledger entry (CM-31-007) | `APPLIED` |
| Duplicate or redelivery of a message the receiver was entitled to act on | `SKIPPED` |
| Buffered out-of-order or pre-genesis ledger entry | `DEFERRED` |

Rules behind the table:

- **`REFUSED` is a protocol outcome, never a bug.** A programming error raises, so
  the dispatcher can still tell the two apart.
- **`SKIPPED` is only for a redundant re-delivery.** A message that reached the
  wrong party is `REFUSED`, so the receiver's record says so.
- **A handler can defer.** `DeferCheckNode` defers before dispatch, but the
  ledger-sync buffer nodes (`core/behaviors/sync/nodes/receive.py`) park an entry
  after dispatch, and that deferral flows through `HandlerDisposition`.
- **`APPLIED` and `SKIPPED` report the same but are different events.** Keep them
  distinct in code even though both read `processed`.
- **The skip helpers return a verdict.** `idempotent_store`
  (`vultron/core/services/idempotent_store.py`) returns `SKIPPED` or `APPLIED`
  for its own act; escalating a skip to `REFUSED` is the calling handler's call.

---

## The verdict chain

Every link from `execute()` to `DispatchNode` returns the `HandlerResult`
(UCORG-05-010). Two links are easy to get wrong:

- **`DispatcherBase._handle()` is the link that calls `execute()`,** not
  `dispatch()`. Typing only the public methods loses the verdict at the first hop.
- **`_handle()` can end without a handler running.** Semantics with no use case
  raise `VultronApiHandlerNotFoundError`, never return, so the outcome is
  `rejected` (UCORG-05-012).

The verdict reaches `InboxOutcome` and the actor log (a `rejected` outcome logs at
WARNING, UCORG-05-013). It never reaches the sender over HTTP: the inbox returns
202 before any handler runs. Telling a remote party about processing outcomes is
a protocol message, not a response code (#2682). A refused status assertion is
answered by the refusal notice alone, never also a `Create(ProcessingFault)`: a
guard's refusal is "received and understood but declined" (MSM-05-001,
CLP-05-001; #4756). A status the adoption gate withholds is `SKIPPED` and gets
neither (RSH-09-008).

---

## Keep the two request paths separate

`VultronEvent` (received: what a remote actor asserted) and `TriggerRequest`
(trigger: what our local actor intends) MUST NOT share a base class. Both carry
`actor_id`, but on an event it is the remote sender and on a trigger it is the
local actor. A shared base would let one parameter accept either and lose the
line between "what they told us" and "what we are doing" (ADR-0040).

---

## Trigger-side contract

- Each `TriggerRequest` is generic in its result subtype, so the one-method port
  `TriggerDispatcher.trigger(request, dl)` resolves each verb's result statically
  (UCORG-05-006); `test_trigger_port_single_method.py` keeps it one method.
- Every result subtype forbids extra keys, so a use case that grows a return key
  fails at construction instead of the key being dropped (UCORG-05-005).
  `activity`, `offer` and `note` stay `dict`s because core cannot import wire
  types (ARCH-01-001).
- Every route under `/trigger/` and `/demo/` is one `run_trigger(...)` call
  (`vultron/adapters/driving/fastapi/trigger_runner.py`) and declares its
  `response_model` (TRIG-12-001). Per-route checks (202, the store passed, the
  queued flush, exact response keys) live once per registry row in
  `test_trigger_routes_contract.py`; router suites keep only the per-verb domain
  assertions and run the real dispatcher (never `Mock(spec=<driving port>)`,
  `vultron/core/ports/AGENTS.md`).

---

## The ratchet is the enforcement

Nothing types a call site against the `UseCase` Protocol, so mypy does not check
`execute()`'s return type. `test/architecture/test_use_case_execute_returns_result.py`
does (UCORG-05-004), and also rejects an `execute()` that takes any parameter
beyond `self` (HP-01-001). Do not cite a ratchet as validation before the test
exists.
