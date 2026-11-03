---
title: Case Event History — Deriving CVD Events From a Case Ledger
status: active
kind: plan
tracks:
  - "#5779"
  - "#5780"
  - "#5781"
  - "#5782"
  - "#5068"
description: >
  Design for the read-only layer that turns a case ledger into the case's CVD event
  history: why events come from state comparison rather than a semantic-type table,
  which events the embargo register and consent rows can only get from the ledger,
  the two clocks and the four data-gap labels, and why no multi-vendor sequence is
  collapsed into one.
related_specs:
  - specs/case-event-history.yaml
  - specs/demo-report.yaml
  - specs/case-ledger-processing.yaml
  - specs/cs-behavior.yaml
  - specs/em-behavior.yaml
  - specs/case-management.yaml
related_notes:
  - notes/case-ledger-parsing.md
  - notes/case-ledger-authority.md
  - notes/case-state-model.md
relevant_packages:
  - vultron/measure
  - vultron/demo
  - vultron/core/states
---

# Case Event History — Deriving CVD Events From a Case Ledger

The reader-facing catalogue of events, clocks and gaps is
`docs/topics/measuring_cvd/what_a_case_records.md`; the symbol table is
`docs/topics/measuring_cvd/_case_events.md`. This note holds the design decisions
the normative requirements in `specs/case-event-history.yaml` do not explain.

## An Event Is a State Change, Not a Message

Derive a report-management, fix-path, deployment or public-state event by comparing
an entry's state against the state already reached, and name the entry's semantic
type as the event's cause (CEH-04-001).

A table keyed on the semantic type alone misses acts. One report-management move has
several wire forms: accepting a stub Invite seats the joiner at Received (CM-11-001),
answering a Full-Case Invite records Valid, Invalid or Closed (CM-11-031), a status
update reports any move, and a `Leave` drives the leaver to Closed through every
intermediate step (CM-23-022). A table that listed `Add(ParticipantStatus)` and
stopped would report no intake events for a joiner at all.

State comparison also gets the count right, because it emits nothing for an entry
that re-reports a state already reached (CEH-04-013) and one event per step for an
entry that moves several (CEH-04-012).

## The Embargo Is the Exception

Embargo start, embargo exit and a participant's consent answer are not dimensions of
a participant status, so state comparison cannot see them. Derive each from the
entry's semantic type and its carried object (CEH-04-005).

An embargo register entry and a consent row each hold a status and no time of their
own. The time of a step is only in the ledger entry that recorded the step, which is
why every embargo measure has to join the two. A consent event names the register
entry it answers, because a case can hold several proposed embargoes at once and a
participant keeps one row per entry (CM-18-001, CEH-04-009).

Keep the three consent answers distinct (CEH-04-008). Inaction is recorded as
`TIMED_OUT` and never as `DECLINED` (CM-18-002), so collapsing them would make a
pocket veto indistinguishable from a refusal and destroy the pocket-veto rate as a
measure.

## Two Clocks Stay Two Fields

Carry the commit stamp and the claimed time in separate fields and never substitute
one for the other (CEH-03-008). They come from different clocks and answer different
questions: all commit stamps in a case come from the CASE_MANAGER's one clock, so any
two of them compare; claimed times from two senders do not (CLP-14-003, CLP-15-003).
An interval inside one participant is better measured on claimed times, because a
fixed offset in that participant's clock cancels out.

A reader that cannot tell which clock a value came from cannot judge whether an
interval means anything, so a single merged time field would make every measure
unfalsifiable.

## Four Gap Labels, Carried on the Event

A measure built on an event inherits that event's gap, so the label belongs on the
event record rather than in each measure's own prose (CEH-03-010). Four of the gaps
in `what_a_case_records.md` change an event's time:

| Label | What it means |
|---|---|
| Seated at creation | The creation sequence committed this status, so its stamp is the creation time (CM-14-009, CM-14-012) |
| Stamped at adoption | The case's public state changed when the CASE_MANAGER committed its own case status, not when a participant first reported it |
| Stamped when next handled | A passing deadline caused the change, and the CASE_MANAGER made it when it next handled the case (EMB-13-003, CM-28-015) |
| Reported out of band | A public exploit or observed attacks happened outside the protocol, and the delay before the report is not recorded |

The other gaps carry no label because they produce no event: refusals and replay
requests are never ledgered (CLP-02-013), an ownership-transfer expiry changes no
participant record (CM-21-043), and the untimed register and consent rows are the
reason for the join described above rather than a gap in an event.

Where the record holds a deadline that bounds the real time better than the stamp,
carry the deadline too (CEH-03-015). An embargo terminated `END_TIME_REACHED` really
ended at the embargo's end time; the commit stamp is only the latest possible end.

## One Sequence per Vendor, None per Case

Project one case-state sequence per participant holding the Vendor or Deployer role,
combining that participant's own fix-path and deployment events with the case's
public-state events (CEH-05-001, CEH-05-003). That is the shape
`replay_cs_history` and `is_valid_cs_history_prefix` read
(`vultron/core/states/cs_invariants.py`), and a single-vendor case yields one
sequence `CVDmodel.score_history` can take.

Do not collapse several vendors into one sequence (CEH-05-006). Vendor awareness and
fix readiness occur once per vendor, and no rule yet says which vendor's event stands
for the case. Choosing one here would settle an open research question without
review; it is tracked as its own work.

Validate every projected sequence as a prefix, and treat a missing event as an
incomplete prefix rather than an invalid history (CEH-05-004, CEH-05-005). Many cases
never see a public exploit or observed attacks, and an open case has not closed, so
an incomplete sequence is the normal result. A sequence that fails the prefix check
means the derivation is wrong, because the CASE_MANAGER refuses an impossible
transition before it commits.

## Read the Canonical Copy; a Merge Reports Its Holes

Only the CASE_MANAGER's ledger is complete. A participant's replica stops receiving
entries while its embargo consent has lapsed and after its report closes
(CM-10-005, CM-23-004), so an event recorded in a gap it missed is absent from its
copy. Prefer that copy when the input holds it (CEH-02-004).

A merge of participant replicas is the fallback, and it must report the log indices
no replica supplied (CEH-02-006). A measure over a history with a hole is wrong
rather than imprecise, so the caller needs to be able to refuse the history instead
of scoring it.

The committed canonical recordings under `ui/src/recordings/` are the test corpus:
each is the CASE_MANAGER's own copy of a real scenario run, with a step list beside
it. They cover an embargo termination, an embargo revision, a refused invitation and
several vendors, so the merge path needs its own fixture (CEH-06-003).

## Reuse the One JSONL Walker

A dimension state sits at several depths and several spellings in a payload snapshot,
and a walker that misses one reports no state for every affected row. The reader is
shared, lives in the measure package, and `vultron/demo/report.py` imports it
(CEH-02-003, CEH-02-009); the rules it implements are in
[case-ledger-parsing](case-ledger-parsing.md).

The demo layer sits above the measure package, so that import goes downward and is
allowed. `vultron-demo-report` keeps its own module, its per-entry grain and its
replica-presence matrix: it is a demo-CI forensic artifact, while the event history
is a research instrument at the event grain.
