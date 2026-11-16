---
source: NOTES-case-event-history--one-sequence-per-vendor-none-per-case
timestamp: '2026-11-16T18:30:58.521906+00:00'
title: One Sequence per Vendor, None per Case
type: note
---

**Archived:** 2026-11-16
**Reason:** delivered and redundant — captured in CEH-05-001 to CEH-05-009, ADR-0174 and ADR-0182; code in vultron/measure/sequences/ and vultron/measure/scoring/. The scoring-entry-point subsection stays in the note as guidance

---

## One Sequence per Vendor, None per Case

Project one case-state sequence per participant **whose events include a
vendor-awareness event**, combining that participant's own fix-path and deployment
events with the case's public-state events (CEH-05-001, CEH-05-003). That is the shape
`replay_cs_history` and `is_valid_cs_history_prefix` read
(`vultron/core/states/cs_invariants/history.py`).

Do not collapse several vendors into one sequence (CEH-05-006). Vendor awareness and
fix readiness occur once per vendor, and no vendor's event stands for the case: a
measure scores each vendor's sequence and summarizes across vendors (ADR-0182).

### Why the key is the event, not the role

Keying on the Vendor **role** builds sequences that cannot replay. A participant
holding the Deployer role but not the Vendor role has no vendor-fix state of its own
(CSB-15-004) and so emits no vendor-awareness and no fix-readiness event, yet it may
legitimately reach fix-deployed. Its sequence would open on `D`, and the case-state
model admits only `vfd`, `Vfd`, `VFd` and `VFD` — `vfD` has no spelling, so
`is_valid_cs_history_prefix` refuses it. The two ephemeral rules (CSB-17-003) make
this sharper: a public-state event with no vendor awareness in front of it obliges `V`
next, so even a public-state-only sequence is refused rather than read as incomplete.

So that participant gets **no sequence, and a stated reason** (CEH-05-007). Its
fix-deployed event stays in the event history, where a measure that needs no
replayable sequence reads it. Reporting the reason rather than an empty list is the
same choice as a merged ledger reporting its holes: silence reads as a participant
with no events, which is a different and wrong answer.

Only a **trailing** event may be missing (CEH-05-005). Many cases never see a public
exploit, and an open case has not closed, so a sequence that stops early is normal. A
*gap* is not: the ephemeral rules forbid it.

### Take each transient state's one way out

Replay the recorded order, and wherever it reaches a transient state whose next
recorded event is not the one that state forces, place the forced event next: move it
up when the ledger records it later, and imply it when the ledger records it nowhere
(CEH-05-009). Mark each with its `Placement` (`MOVED`, `IMPLIED`). A moved event
keeps its log index and clocks; an implied one carries those of the event that
reached the transient state. The event history stays as recorded. Reason: `pX` and
`vP` are transient (CSB-17-003). A published exploit makes the public aware at once,
and an aware public makes the vendor aware at once, so an event in between is
independent and the record merely trails. Recorded `P, X, V` is `P, V, X`; `X, V, P`
is `X, P, V`; `V, X, A` is `V, X, P, A` (decided by the project owner on PR #6283).

Derive the forced event from `required_next_cs_events`; never restate it in a table.
Reason: one state model, and a test pins that each transient state has exactly one
way out. With both, every order one vendor's and the case's events can be recorded in
projects; only an entry a CASE_MANAGER would refuse, such as a fix deployed before it
is ready, is still reported not a valid prefix (CEH-05-004, CEH-05-007). The code is
`vultron/measure/sequences/` (`case_state_sequences`, `SequenceEvent.placement`).

### The prefix check is this layer's, not the CASE_MANAGER's

A sequence that fails the prefix check means the derivation is wrong or the recorded
order holds an entry the CASE_MANAGER would refuse — never that it already refused
the transition. It validates a participant's
dimensions and the case's public state *separately*, and skips any rule that reads a
dimension the participant does not have (`composite_state_violations`, and
`_compound_violations` returns no violation whenever the participant's `vf` is absent).
That is ADR-0075's deliberate design. A ledger whose every entry the CASE_MANAGER
accepted can therefore still project a compound sequence that does not replay. This
layer builds the compound, so this layer owns the check (CEH-05-004).

### The layer stops at the sequence

It computes no score (CEH-05-008). The existing desiderata scorer is
`CVDmodel.score_hist` in `vultron/core/case_states/hypercube/_scoring.py` — note the
name —
and it admits only a *complete* six-event history, raising `ScoringError` on anything
shorter. Every sequence the committed recordings yield is incomplete, so that scorer
has nothing to score for a typical case. The measures stay out of this layer: an
incomplete sequence is scored by `vultron/measure/scoring/` (`score_sequence`), which
reads the sequence and never the other way round (ADR-0182).
