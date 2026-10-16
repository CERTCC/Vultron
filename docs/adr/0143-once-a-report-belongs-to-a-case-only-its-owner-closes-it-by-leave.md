---
status: accepted-provisional
date: 2026-10-16
created: 2026-10-16
updated: 2026-10-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0050, ADR-0085, ADR-0115; specs/case-management.yaml
  CM-23-001, CM-23-018
informed: []
stakeholder_type: [project-contributor]
---

# Once a Report Belongs to a Case, Only Its Owner Closes It, by Leave

## Context and Problem Statement

A `Close(Report)` (`Reject(Offer(VulnerabilityReport))`) declares that its sender's RM state is `CLOSED`.
The CASE_MANAGER admitted one from any participant of the case and moved the sender to `CLOSED`.
The Case Owner closes a case by `Leave(VulnerabilityCase)`, which also commits `case_fully_closed` (CM-23-002).
So the owner's own `Close(Report)` moved it to `CLOSED` while the case stayed open, and the guard for the `CASE_OWNER` standing did not check closure, so the closed owner kept its owner acts (#4746).

What should a `Close(Report)` mean once the report belongs to a case?

## Decision Drivers

- A case has one closing act, the Case Owner's `Leave`, and the CASE_MANAGER's ledger is its authority (CM-23-001).
- Once a case holds the report, the Case Owner is the only holder of it; nobody else has a report to close.
- A participant whose closure the case records may act on nothing further (CM-23-018).
- A wrong message is refused, not reinterpreted.

## Considered Options

- **A — Refuse `Close(Report)` on a case from every sender.**
- **B — Treat the owner's `Close(Report)` as a full close**, as if it were the owner's `Leave`.
- **C — Keep admitting `Close(Report)`, and refuse a closed owner's later acts.**

## Decision Outcome

Chosen option: **A**.

Once a report belongs to a case, the CASE_MANAGER refuses a `Close(Report)` for it from every sender, with nothing written, committed or sent.
From the Case Owner it is the wrong closing act; the owner closes the case by `Leave(VulnerabilityCase)`.
From any other sender it is a message about a report that sender does not hold.
An actor's own trigger that would send `Close(Report)` for a report a case holds fails before it sends anything.
A `Close(Report)` for a report that belongs to no case is unchanged.

Other paths can still leave a Case Owner at RM `CLOSED` on an open case (a status update declaring it, a `Leave` whose later commit fails).
So the guard composed for the `CASE_OWNER` standing also refuses an owner whose closure the case records, as CM-23-018 requires of every sender.

Option B was rejected: it gives the case two closing messages, and the `Leave` round-trip, which declines a close while an embargo is active (CM-23-011), would have a bypass.
Option C was rejected: it keeps a message admitted that no sender should send once a case exists, and closes only the owner half of the problem.

### Consequences

- Good, because the case has exactly one closing message, and the owner cannot leave its case open behind it.
- Good, because a closed owner, however it reached `CLOSED`, holds no owner standing.
- Bad, because the close-report trigger has no success path once a case exists, and the reject-report trigger fails on a case too; an operator closes with close-case instead.
- Neutral, because the `PreCloseAction` call-out sits on the close-report trigger, so it does not run on a case; where it belongs is left to its own decision (#4815).

## Validation

- A received-use-case test drives `Close(Report)` on an open case from the Case Owner and from a participant that is not the owner, and asserts `REFUSED` with no RM change, no ledger entry and nothing sent.
- Trigger tests assert the close-report and reject-report triggers fail on a case with nothing written or queued.
- For every use case declaring the `CASE_OWNER` standing, a test asserts a closed Case Owner is refused.

## More Information

- ADR-0050 — RM closure by `Leave(VulnerabilityCase)`.
- ADR-0115 — received handlers check their sender's entitlement.
- #4746 — the bug this record answers.

Generated spec requirements: `case-management.yaml` CM-23-019.
