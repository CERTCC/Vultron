---
status: proposed
date: 2026-10-16
created: 2026-10-16
updated: 2026-10-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0050, ADR-0110, ADR-0144; specs/case-management.yaml
  CM-23-001, CM-23-011, CM-23-016, CM-23-019; specs/triggerable-behaviors.yaml
  TRIG-02, TRIG-08
informed: []
stakeholder_type: [project-contributor]
---

# A Case Is Left Through the Leave-Case Trigger, Whose Actor Runs Its Pre-Close Step First

## Context and Problem Statement

Once a case holds a report, the CASE_MANAGER refuses a `Close(Report)` for it from every sender, and an actor's own trigger that would send one fails before it sends anything (CM-23-019, ADR-0144).
The `close-report` trigger needs a case: it resolves the report's linked case and fails when there is none.
So it has no success path left.
A report that no case holds is closed with `reject-report`.

The `PreCloseAction` Actuator call-out, the capability model's "perform any pre-closure integration actions", is wired into no core tree but the `close-report` trigger's, so it no longer runs.
Its sibling, the `OtherCloseCriteriaMet` Evaluator, sits in a tree builder that nothing calls.

The trigger that sends `Leave(VulnerabilityCase)`, `close-case`, is demo-only, so it is not mounted in production mode (TRIG-02-006, TRIG-09-002).
So a production deployment already has no trigger that closes its part in a case, and retiring `close-report` alone would not give it one.

The question this record settles: how does an actor close its part in a case through the trigger API, and where does its pre-close step run?

## Decision Drivers

- Past the point where a case exists, an actor closes by leaving the case, never by closing the report (CM-23-001, ADR-0050).
- A trigger with no success path is an API surface that only returns errors.
- Leaving a case is an actor decision an operator or agentic client makes, so it is a general-purpose trigger (TRIG-08-002).
- The pre-close step is the leaving actor's own integration work, such as closing its ticket, not the CASE_MANAGER's.
- Applying a ledger entry to a replica copies objects and runs no lifecycle logic or local policy (CM-23-016).

## Considered Options

- **A — Retire `close-report`; expose `leave-case` as a general-purpose trigger; run `PreCloseAction` in it before the Leave is sent.**
- **B — Keep `close-report` as an endpoint that always fails; move `PreCloseAction` only.**
- **C — Keep both as they are and document `PreCloseAction` as unreachable.**

For where `PreCloseAction` runs under A:

- **A1 — On the leaving actor's side, before it sends the Leave, for every participant.**
- **A2 — After the CASE_MANAGER admits the Leave, when the actor's replica applies the entry that records its closure.**

## Decision Outcome

Chosen option: **A, with A1**.

The `close-report` trigger, its use case and its tree are removed.
The demo-only `close-case` trigger is replaced by a general-purpose `leave-case` trigger that any participant may call.
It sends `Leave(VulnerabilityCase)` to the CASE_MANAGER, which decides what the Leave means: a participant that is not the owner departs, and the Case Owner's Leave closes the case (CM-23-002, CM-23-003).
The verb is named for the message it sends, because for most callers the case stays open.

`leave-case` runs `PreCloseAction` before it sends the Leave, for every caller.
When the caller is the Case Owner and its replica records an active embargo, the trigger fails before the call-out runs, with an error that says to terminate the embargo first.
That is the check the CASE_MANAGER makes on receipt (CM-23-011), made before the actor's own systems act on a close that would be declined.

`OtherCloseCriteriaMet` asked "should this actor close now?" when the actor's behavior was one tree that ran every check on each tick.
Triggers now start each act, so that decision is the act of calling `leave-case`, and the call-out is superseded.

Option B was rejected: it keeps a client-visible endpoint whose only behavior is an error.
Option C was rejected: it leaves production with no closing trigger and the pre-close step with no caller.
Option A2 was rejected: it puts a deployment's own action into replica application, which CM-23-016 limits to copying, and it would need a design of its own.

### Consequences

- Good, because a participant that has joined a case has one trigger that closes its part in it, and production deployments can call it.
- Good, because the pre-close step runs for every participant that leaves, not only the owner.
- Good, because the Case Owner's systems do not act on a close the CASE_MANAGER would decline for an active embargo.
- Bad, because removing `close-report` and the demo `close-case` route is a client-visible API change, so the committed OpenAPI trigger snapshot moves.
- Bad, because `PreCloseAction` runs before the CASE_MANAGER answers, so it can still act on a Leave that is refused for another reason.
- Neutral, because the `OtherCloseCriteriaMet` call-out stays in the code, unwired, and the capability model marks it superseded.

## Validation

- Trigger tests drive `leave-case` from a participant that is not the owner and from the Case Owner, and assert `Leave(VulnerabilityCase)` addressed to the CASE_MANAGER, with `PreCloseAction` run first.
- A trigger test drives `leave-case` from the Case Owner with an active embargo and asserts the trigger fails with nothing sent and the call-out not run.
- The trigger registry has no `close-report` row and no demo `close-case` row, and the OpenAPI snapshot is regenerated in the same change.

## More Information

- ADR-0050 — RM closure by `Leave(VulnerabilityCase)`.
- ADR-0110 — the verb-keyed trigger registry.
- ADR-0144 — once a report belongs to a case, only its owner closes it, by `Leave` (#4746).
- #4815 — the concern this record answers.

Generated spec requirements: `triggerable-behaviors.yaml` TRIG-02-001, TRIG-02-004, TRIG-02-006, TRIG-13-001, TRIG-13-002, TRIG-13-003.
