---
status: proposed
date: 2026-10-09
created: 2026-10-09
updated: 2026-10-09
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0085, ADR-0111; specs/case-management.yaml CM-23-013;
  specs/message-semantics-mapping.yaml MSM-05-001
informed: []
stakeholder_type: [project-contributor]
---

# Post-Close Traffic Is Dropped, and Only a Late Leave May Be Answered

## Context and Problem Statement

ADR-0085 made owner close a hard write boundary.
CM-23-013 states the rule: after `case_fully_closed` is committed, the CASE_MANAGER records nothing for any inbound activity on the case and changes no case or participant state.
It MAY reply with an `as:Reject` or MAY drop the activity with no reply.

The reference implementation has to pick one, at one configuration point, with a default (#4162).
A general `as:Reject` reply is not safe.
The reply wraps the late activity, and a Reject that wraps most activities already carries a protocol meaning for its recipient.
`Reject(Invite)` is a declined invitation, `Reject(Offer(CaseParticipant))` a declined recommendation, and `Reject(Offer(VulnerabilityCase))` a declined ownership transfer.
A sender that receives one of these after close would read it as a decision on its request, not as "the case is closed".

## Decision Drivers

- A reply must not be misread as a protocol decision (MSM-05-001).
- The CASE_MANAGER of a closed case should behave like a process that has exited (CM-23-013).
- One policy point, with a default, so a deployment can change the choice without a code change.
- No new wire message unless one is needed.

## Considered Options

- **A — Drop by default; a Reject setting answers only a late Leave.**
- **B — Drop by default; a Reject setting answers every late activity**, with a new Reject shape that cannot be confused with an existing one.
- **C — Reject by default, for every late activity.**

## Decision Outcome

Chosen option: **A**.

`ActorConfig.post_close_reply` is the one policy point.
Its default is `drop`: the CASE_MANAGER sends nothing for any activity that arrives after `case_fully_closed`.
With `reject`, it answers a late `Leave(VulnerabilityCase)` with `Reject(Leave(VulnerabilityCase))`.
That reply already means "close declined" (CM-23-011), so it cannot be misread.
Every other late activity is dropped with no reply under both settings.
Under both settings the handler reports `REFUSED` and logs the drop at INFO with the activity id, the sender's actor id, and the case id.

The boundary is one guard that the received-tree factory, `create_receive_activity_tree`, places in every received tree directly after intake (ADR-0111), so no handler can omit it.
At the case's CASE_MANAGER, once the ledger holds `case_fully_closed`, the guard fails the tree before the receipt commit and every effect.
On every other store it passes, so replicas still apply the closure fan-out.
The resync tree (`Reject(CaseLedgerEntry)`) is exempt, because a replay appends nothing (ADR-0085).
A handler that commits or sends before its tree runs asks the same guard first, as a one-node preflight, so the rule still lives in one node.

Option B was rejected for now: it needs a new wire message and its own semantic pattern, and no participant needs a reply to non-Leave traffic.
CM-23-013 already tells participants not to rely on one.
Option C was rejected: it would send misreadable replies by default.

### Consequences

- Good, because no reply can be misread, and no new wire message is needed.
- Good, because the default matches an exited process, which is what CM-23-013 describes.
- Bad, because a participant that sends non-Leave traffic after close is never told why it was ignored.
  A later ADR can add option B if that becomes a need.
- Neutral, because the Reject setting changes only the reply to a late Leave; the recorded state is the same under both settings.

## Validation

- `test/core/use_cases/received/test_close_case_role_semantics.py::TestPostCloseWriteBoundary` drives a late Leave under both settings, confirms the default is `drop`, confirms a late `Add(Note)` gets no reply under both settings through the inbox dispatcher, and confirms the INFO log line.
- `test/core/behaviors/case/test_receive_activity_tree.py::TestPostCloseStage` confirms that every received tree carries the guard and that only an exempt tree omits it.
- `test_invariant_18_no_participant_act_after_case_fully_closed` confirms, over each demo scenario's exported ledger, that no participant act follows `case_fully_closed`.

## More Information

- ADR-0085 — owner close is a hard write boundary.
- ADR-0111 — intake is the first received-side stage.
- CM-23-013, CM-23-017 — the post-close rule and its reference-implementation policy point.
- VP-03-013 — recipients may ignore messages of any class on closed cases.
- #4162, #4065, #3060 — the issues this decision closes.
