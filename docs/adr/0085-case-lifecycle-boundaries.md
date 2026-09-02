---
status: accepted
date: 2026-09-02
deciders: Allen D. Householder
consulted: Claude Opus 4.8
informed: []
---

# Owner-Close Is a Hard Write Boundary; RM.CLOSED Is Terminal and Rejoin Is Unsupported

## Context and Problem Statement

Owner closure is specified as *global and terminal* — a "permanent Leave" that
closes the case for all participants (CM-04-007, ADR-0050). But the protocol
never states what that terminal state means for **inbound activities**, and the
RM state machine has no exit from `RM.CLOSED`. Two gaps result:

1. **The post-owner-close message boundary is unspecified (CONCERN-1894).** The
   only post-close rules (`VP-03-013`, `RMB-14-002`) are permissive *MAY-ignore*
   rules scoped to R\* (RM) messages. `Add(Note)` is a General-Inquiry (GI)
   message, not R\*, and nothing addresses it — the reference note handler has no
   closed-case guard and persists post-close notes today. Independent
   implementations can each drop, accept, or selectively accept post-close
   traffic and all claim conformance.

2. **`RM.CLOSED` is terminal with no rejoin path (CONCERN-1918).** A participant
   that sends `Leave(VulnerabilityCase)` advances to `RM.CLOSED`. There is no
   defined transition out, so a departed participant that later wants back in has
   no protocol path.

A related concern, **CONCERN-1902**, observes that `SvcCloseCaseUseCase` (the
report-phase closure path) is never reached because the reference process
auto-creates the case before report validity is evaluated.

## Decision Drivers

- Owner-close is defined as terminal and global; the canonical case history
  must not keep growing from external writers after the owner has closed the
  case.
- A single, stated rule is required so independent implementations converge
  rather than each inventing a post-close policy.
- Rejoin raises unresolved design questions (multiple lifecycle arcs per actor,
  `actor_participant_index` is one slot per actor, whether `RM.CLOSED` should
  become non-terminal) that are larger than this session can settle.
- A workable interim path for "I might come back" already exists in the state
  machine.

## Considered Options

### Post-close message boundary

- **A — Hard kill switch.** After owner-close, the Case Actor accepts no new
  external ledger writes at all.
- **B — Selective gate.** Some activity classes (e.g. notes / GI) remain
  permitted while R\* is refused.
- **C — Generalize MAY-ignore.** Extend the permissive "MAY ignore" rule from
  R\* to all message types, making current behavior explicit.

### Rejoin

- **A — Reactivate the same participant record** (make `RM.CLOSED` non-terminal).
- **B — New participant record via re-invitation.**
- **C — `RM.CLOSED` stays terminal; rejoin unsupported**, with a defer-not-close
  workaround.

## Decision Outcome

**Post-close boundary: Option A — hard kill switch.**
**Rejoin: Option C — `RM.CLOSED` terminal, rejoin unsupported.**

### Post-close write boundary (the locked front door)

When the Case Owner sends `Leave(VulnerabilityCase)`, the Case Actor commits and
broadcasts the closure — `Announce(CaseLedgerEntry(Leave(Case, actor=Owner)))` —
and thereafter accepts **no new ledger entries from external participants**. The
metaphor is a store at closing time: when the owner leaves, the front door locks,
even if staff are still tidying up inside.

- `Leave(VulnerabilityCase)` from the owner is the owner saying "I'm done here."
  The `Announce(CaseLedgerEntry(...))` from the Case Actor is the closure
  announcement to participants. The Case Owner MAY wait for that announcement to
  land before exiting its own process.
- After emitting the closure announcement, the Case Actor MAY continue to service
  resync / replay requests (implementer's choice) but MUST NOT append anything
  new to the case ledger on behalf of an external participant.
- The note handler (`AddNoteToCase`) and analogous handlers MUST gain a
  closed-case guard; a post-close inbound that would append to the ledger is
  refused.
- An inbound message arriving on a closed case MAY prompt the **Case Owner** with
  an option to **reopen** the case. Reopen is Case-Owner-only. Its mechanics are
  **not** decided here (see Deferred).

Option B was rejected: there is no principled line between note-like and other
GI traffic, and it lets canonical history grow after close. Option C was rejected:
"MAY reject" is not "MUST reject," so implementations would still diverge — the
ambiguity CONCERN-1894 filed.

### Rejoin: closed is terminal, defer-don't-close is the workaround

`RM.CLOSED` remains terminal. There is no rejoin transition. A participant that
anticipates it might return SHOULD move to `RM.DEFERRED` (the parking lot) rather
than closing: `DEFERRED` is resumable (`DEFER: ACCEPTED → DEFERRED` and
`ACCEPT: DEFERRED → ACCEPTED` both exist), whereas `CLOSED` is not. `DEFERRED` is
a shallow sleep; `CLOSED` is a deep sleep from which there is no reawakening in
this design.

Options A and B were rejected: A requires RM state-machine surgery and breaks the
single-flow-per-participant-record property; B creates a second participant record
for one actor and collides with `actor_participant_index`, which holds one slot
per actor.

### CONCERN-1902 — no code change

Auto-create-case is an **implementation choice** made by the reference/demo
process, not a protocol requirement. `SvcCloseCaseUseCase` is the closure path
for implementations that do *not* auto-create; it is already unit-tested
(`test/core/use_cases/triggers/test_close_case_trigger.py`,
`test/core/behaviors/report/test_trigger_report_trees.py`). CONCERN-1902 resolves
to a spec clarification that auto-create-case is an implementation choice; no new
code is required.

### Consequences

- Good: post-close behavior is one stated rule; implementations converge, and the
  canonical history stops growing after owner-close.
- Good: the rejoin design tension is not forced prematurely; a real interim path
  (defer-don't-close) exists today.
- Neutral: reopen is acknowledged as possible but its mechanics are deferred, so
  a closed case cannot yet be reopened in the reference implementation.
- Bad: the note handler and analogous handlers need a new closed-case guard, and
  `VP-03-013` / the RM-behavior satisfiers must be broadened beyond R\*.

## Validation

- A test asserts a post-close `Add(Note, target=Case)` is refused (no ledger
  append) rather than persisted.
- A test asserts the Case Actor emits the closure `Announce(CaseLedgerEntry)`
  before ceasing external writes.
- Existing `SvcCloseCaseUseCase` trigger tests continue to pass; a spec entry
  records that auto-create-case is an implementation choice.
- Spec amendments in `specs/case-management.yaml`, `specs/rm-behavior.yaml`, and
  `specs/vultron-protocol-spec.yaml` broaden the post-close rule beyond R\* and
  state the kill-switch boundary.

## More Information

- CONCERN-2833 (planning group G05) — session that produced this decision
- CONCERN-1894 — post-owner-close message boundary is unspecified (source)
- CONCERN-1918 — rejoin semantics for departed participants (source)
- CONCERN-1902 — `SvcCloseCaseUseCase` unreachable under auto-create-case (source)
- ADR-0050 — `Leave(VulnerabilityCase)` is the canonical RM closure mechanism
- ADR-0084 — Participant Assertion Authority (companion decision)
- Deferred: post-join role change (`Update(CaseParticipant)`) and case reopen
  mechanics are tracked as Ideas under Epic #2567.
