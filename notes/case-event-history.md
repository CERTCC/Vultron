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
  - "#6067"
  - "#6068"
  - "#6069"
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
related_adrs:
  - docs/adr/0174-cvd-measures-read-a-case-ledger-through-a-read-only-event-history.md
  - docs/adr/0182-cvd-measures-take-chance-from-the-smallest-model-holding-each-desideratum.md
  - docs/adr/0075-split-vfd-state-machine.md
  - docs/adr/0060-re-express-legacy-cs-invariants.md
relevant_packages:
  - vultron/measure
  - vultron/demo
  - vultron/core/states
---

# Case Event History — Deriving CVD Events From a Case Ledger

The reader-facing catalogue of events, clocks and gaps is
`docs/topics/measuring_cvd/what_a_case_records.md`; the symbol table is
`docs/topics/measuring_cvd/_case_events.md`. The decisions that weighed an
alternative and rejected it are in ADR-0174. This note holds the rest of the design
— the reasoning, the layout, and the traps — that neither the record nor the
normative requirements in `specs/case-event-history.yaml` carry.

## An Event Is a State Change, Not a Message

Derive a report-management, fix-path, deployment or public-state event by comparing
an entry's state against the state already reached, and name the entry's semantic
type as the event's cause (CEH-04-001).

A table keyed on the semantic type alone misses acts. One report-management move has
several wire forms: accepting a stub Invite seats the joiner at Received (CM-11-001),
answering a Full-Case Invite records Valid, Invalid or Closed (CM-11-011), a status
update reports any move, and a `Leave` drives the leaver to Closed through every
intermediate step (CM-23-022). A table that listed `Add(ParticipantStatus)` and
stopped would report no intake events for a joiner at all.

State comparison also gets the count right, because it emits nothing for an entry
that re-reports a state already reached (CEH-04-013) and one event per step for an
entry that records several at once (CEH-04-012). A case closure is **not** such an
entry: CM-23-022 commits one entry per report-management transition, so the leaver's
`V → D → C` is three entries. The genesis entry is the real example — it seats the
CASE_MANAGER's own participant at Received, Valid and Accepted together.

Two things state comparison sees that are not events. An entry may carry a whole
participant object as a *recommendation* for an actor not yet in the case, at
`RM.START`, several entries before that actor's real record exists; deriving from it
would date the actor's first event to before it was invited (CEH-04-014). And an entry
may name a state *behind* the one already reached, which is a change but not a forward
one — it is excluded from the events and reported, never emitted as a backward step
(CEH-04-015, CEH-04-016).

## What the Derivation Reads

These rules live in `vultron/measure/history/` (`derive.py`, `snapshot.py`).

- **Read only the activity's carried `object`.** An `Add(ParticipantStatus)`'s
  `target` holds the participant as stored when the snapshot was taken, which can
  already hold the statuses the next entries add: in `rccv-extension` entry 48's
  target holds the `CLOSED` that entry 49 records (CM-23-022).
- **Identify a status by its `id`.** A carried participant or case repeats its whole
  status list, so a status seen before is a restatement, never a regression; only an
  unseen status is compared with the state reached (CEH-04-013, CEH-04-015).
- **Skip everything under an `Offer`.** A recommendation and an ownership offer both
  carry copies that are not the record's own state (CEH-04-014).
- **Read the case's public state from case statuses only.** A case status nested in
  a participant status is that participant's report; adoption is the event
  (CEH-03-012).
- **Activation is the owner's consent.** The Case Owner's `Add(EmbargoEvent)` makes
  its own row `AGREED`, and a revision ending no later carries every signatory over,
  so derive both from the activation entry rather than from a later snapshot that
  shows the row (CM-10-001, `EmbargoLifecycle` activation).
- **The creation sequence is genesis plus the CASE_MANAGER's unbroken run after it.**
  Its events carry the seated-at-creation label (CM-14-001, CEH-03-011).

## Joining Is the Other Exception

Joining has no state change of its own, so state comparison cannot see it, and the
entry that *first* records a participant is the wrong entry to use. The CASE_MANAGER
creates an invitee's `CaseParticipant` at `RM.RECEIVED` in its own entry while the
participant is still inert (CM-11-006), and accepting the stub Invite then *leaves*
report management at `RM.RECEIVED` (CM-11-001). So the only entry a "first records the
participant" rule can find is the one that predates joining.

Key the joining event on the **acceptance** entry instead (CEH-04-010). An inert
participant's seated state is held until then and emitted at the acceptance entry, so
a joiner's joining and report-received events share a log index; an invitee that
never accepts yields only its consent answer. That is also
what keeps a joining event off a participant that never joined: a refused invitation
and an expired one both leave the inert record untouched, so the creation entry is
there for them too. In the `rcv-reject` recording the invitee is seated, then the
invitation is rejected two entries later — a "first records" rule would report that
actor as having joined.

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

The claimed-time field is absent-able even though a conforming entry always states one
(CLP-15-006, and CLP-15-008 refuses an inbound activity carrying no `published`). This
layer is handed archived and foreign ledgers it never validated, and an absent claimed
time has to read as absent rather than as a commit stamp copied into its place
(CEH-03-007, CEH-03-008).

## Four Gap Labels, Carried on the Event

A measure built on an event inherits that event's gap, so the label belongs on the
event record rather than in each measure's own prose (CEH-03-010). Four of the gaps
in `what_a_case_records.md` change an event's time:

| Label | What it means |
|---|---|
| Seated at creation | The creation sequence committed this status, so its stamp is the creation time (CM-14-009, CM-14-012) |
| Stamped at adoption | The case's public state changed when the CASE_MANAGER committed its own case status, not when a participant first reported it |
| Stamped when next handled | A passing deadline caused the change, so the stamp may lag it; the event carries the deadline (EMB-13-003, CM-28-015, CEH-03-015) |
| Reported out of band | A public exploit or observed attacks happened outside the protocol, and the delay before the report is not recorded |

The other gaps carry no label because they produce no event: refusals and replay
requests are never ledgered (CLP-02-013), an ownership-transfer expiry changes no
participant record (CM-21-043), and the untimed register and consent rows are the
reason for the join described above rather than a gap in an event.

The "stamped when next handled" label says the stamp may lag the deadline that caused
the change. Put it on every `END_TIME_REACHED` exit the CASE_MANAGER commits, and on
every timed-out invitation (CEH-03-013). EMB-13-003 reaches an end-time exit two ways,
the CASE_MANAGER's own lazy check and an outside request such as a Sentinel's, and the
ledger records both as the same `Remove(EmbargoEvent)` with no requester. So the label
cannot tell the paths apart, and the deadline the event carries (CEH-03-015) is what
gives the true end time. An end-time exit some other actor committed is not labelled.

Where the ledger holds a deadline that bounds the real time better than the stamp,
carry the deadline too (CEH-03-015). An embargo terminated `END_TIME_REACHED` really
ended at the embargo's end time; the commit stamp is only the latest possible end.
The deadline is not always on the entry recording the event: a timed-out invitation
carries none of its own, because CM-28-013 lets only an `INVITED` consent row hold an
RSVP deadline and the row has already moved to `TIMED_OUT`. Carry it forward from the
earlier entry that recorded the invitation.

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

### A vendor aware only after the exploit is public does not replay

Report such a vendor unprojectable as not a valid prefix, never raise and never
drop it (CEH-05-004, CEH-05-007). Reason: the ledger is valid — the CASE_MANAGER
moves the public state through `P` and `X` in its own machine, and a joining
vendor's first fix-path status has nothing to compare a compound against — yet
`P, X, V` breaks the `vP` ephemeral rule (CSB-17-003). The single-vendor model
cannot place a vendor that joins late, so a raise would lose every other vendor's
sequence over a real case. Projection lives in `vultron/measure/sequences/`
(`case_state_sequences`).

### The prefix check is this layer's, not the CASE_MANAGER's

A sequence that fails the prefix check means the derivation is wrong or the case
outran the single-vendor model, as above — never that the CASE_MANAGER already refused
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
shorter. Every sequence the committed recordings yield is incomplete, so there is no
score to compute for a typical case. How an incomplete sequence earns a score is
decided by ADR-0182 and built by #6068; the measures stay out of this layer.

### Measures built on these sequences take chance per vendor

A measure scores each vendor's sequence against a baseline from the smallest model
that holds the desideratum's events: one vendor and the case's shared events, or two
vendors for a desideratum relating them (ADR-0182). Reason: a walk over the whole
case grows with the participant count, and its baselines change with that count, so
no table would serve every case. Do not build a whole-case walk, and do not key a
baseline on the number of participants. An incomplete sequence is scored through its
completions under the same walk (expected, best and worst), and a case reports
per-vendor scores with their unweighted median and spread.

Score through `vultron.measure.baselines`, never a second walk: its
`completion_probabilities(prefix)` weights each six-event completion from where the
case stands, and `frequency` serves any joint-model query. Reason: one walk keeps
the completions and the baselines under the same chance model (ADR-0182). Its joint
models obey only enforced rules — a SHOULD never constrains them, because the
desiderata measure exactly those preferences.

## Read the Canonical Copy; a Merge Reports Its Holes

Only the CASE_MANAGER's ledger is complete. A participant's replica stops receiving
entries while its embargo consent has lapsed and after its report closes
(CM-10-005, CM-23-004), so an event recorded in a gap it missed is absent from its
copy. Prefer that copy when the input holds it (CEH-02-004).

Identify it from the **entries**, never from the path (CEH-02-009). A recording's
ledger file is named for neither its actor nor its role: the committed recordings are
`ui/src/recordings/<scenario>/case-actor.jsonl`, while a demo run writes
`<actor>-case-ledger.jsonl` under a directory named for the actor. A path-derived
answer misreads the scenario name as the actor name, finds no CASE_MANAGER, and sends
every recording down the merge path to be reported as holed.

No entry names the copy's holder: a replica's entry is byte-identical to the
CASE_MANAGER's (CLP-07-013). So the layer identifies the copy by **completeness**: a
copy is read alone when it holds one entry at each index from `0` up with no gap
(CLP-14-010) and every entry hash any other copy of the case holds
(`vultron/measure/ledger/copies.py`). The CASE_MANAGER's copy always passes.

Completeness is known only relative to the input, so carry the end separately. A
replica cut off at the tail, as when its report closed, passes when no fuller copy is
handed over, and the result calls it a complete copy with no holes. `end_confirmed`
is set only when the entries prove nothing follows the last entry
(`vultron/measure/ledger/ends.py`). Two things prove it: the last entry is the
CASE_MANAGER's own closure (`closure_boundary_indices`, CM-23-013), or another copy
ends on the same entry. A measure that needs the whole case refuses a history whose
end is unconfirmed. Do not try to name the copy's holder: the entries cannot say it
(decided for #5779).

Two copies holding different entries at one index, or one entry hash with two
different bodies, are reported, never resolved: a conforming ledger has none, so a
history over one is not to be trusted, and keeping either body would pick by file
order. A bad row that names another case does not make a file's copy incomplete; only
a row that names no case might be the missing entry.

For the same reason the layer takes its files from the caller and globs for nothing
itself (CEH-02-003, CEH-02-010). `vultron-demo-report` keeps its own
`**/*-case-ledger.jsonl` discovery in `vultron/demo/report/timeline.py`, which
DRPT-01-007 pins; that glob matches none of the committed recordings, so a layer that
inherited it could not open its own test corpus.

A merge of participant replicas is the fallback, and it must report the log indices
no replica supplied (CEH-02-006). A measure over a history with a hole is wrong
rather than imprecise, so the caller needs to be able to refuse the history instead
of scoring it.

The committed canonical recordings under `ui/src/recordings/` are the test corpus:
each is the CASE_MANAGER's own copy of a real scenario run, with a step list beside
it. They cover an embargo termination, an embargo revision, a refused invitation and
several vendors.

### What the corpus does not cover

Five requirements rest on ledger data no recording holds, so each needs a hand-built
fixture or it passes with nothing exercising it (CEH-06-003, CEH-06-006):

| Not in any recording | Leaves untested |
|---|---|
| A ledger with no CASE_MANAGER copy | the merge path and its reported holes |
| An embargo ended `END_TIME_REACHED` — every recording ends early with a cause | the end-time exit, its label and its bounding deadline |
| A `DECLINED` or `TIMED_OUT` consent row — every row is agreed, invited or uninvited | two of the three distinct consent answers |
| A Deployer holding no Vendor role — the one deployer also holds Vendor | the unprojectable participant |

This is why the prefix check over the recordings cannot stand alone as the derivation
test: the corpus is missing exactly the shapes that break a naive derivation.

## Reuse the One JSONL Walker

A dimension state sits at several depths and several spellings in a payload snapshot,
and a walker that misses one reports no state for every affected row — which a measure
cannot tell from a state the case never reached. That tolerance is the requirement
(CEH-02-002); the rules it implements are in
[case-ledger-parsing](case-ledger-parsing.md).

**Where the code goes** is a layout choice, so it lives here rather than in the spec,
which states only the boundary that nothing in the protocol path imports the layer
(CEH-01-001):

- The layer is `vultron/measure/`, outside the protocol path. Each stage is a
  subpackage that reads through the one below it: the event history is
  `vultron/measure/history/` (`case_event_history`, `read_case_event_histories`),
  a sibling of `ledger/`, never part of it. The per-vendor case-state sequences are
  `vultron/measure/sequences/` (`case_state_sequences`), reading only the history.
  The chance baselines (`vultron/measure/baselines/`) read only
  `vultron/core/states/`, never a ledger.
- `vultron/measure/ledger/` is the reader every measure shares: `fields.py` (the
  tolerant field accessors and the dimension-state walker), `names.py` (the
  display-name resolver), `jsonl.py` (the tolerant file reader), `copies.py`
  (per-case complete-copy selection, merge and holes) and `ends.py` (whether the
  entries confirm the ledger's end). Its public names are
  re-exported from `vultron.measure.ledger`; import from there.
- The walker came out of `vultron/demo/report/`, and the report tool imports it from
  `vultron.measure.ledger`. The demo layer sits above the measure package, so that
  import goes downward; nothing in `vultron/measure/` imports `vultron.demo`.
- The display-name resolver (`collect_actor_names`, `friendly_actor_name`) moved down
  with it. Left in the demo layer, it would make the two packages import each other.
  Its URI fallback is `vultron.core.display.friendly_name`, not a second copy.
- `discover_replicas` stays in `vultron/demo/report/timeline.py` with its glob.
- Two architecture tests in `test/architecture/test_measure_layer_boundaries.py`
  hold the layer's boundaries: no protocol-path import (CEH-01-001) and no write
  (CEH-01-002). A command that writes its own output file is admitted by name in
  that test's `OUTPUT_FILE_WRITERS`.

`vultron-demo-report` keeps its own module, its per-entry grain and its
replica-presence matrix: it is a demo-CI forensic artifact, while the event history
is a research instrument at the event grain.

### One tolerant reader, one strict wrapper

The two tools want opposite things from a malformed row. DRPT-01-004 has
`vultron-demo-report` exit non-zero when a file cannot be parsed. The measure layer
must instead degrade one bad row to one unusable entry and finish the rest, reporting
the row (CEH-02-008) — a single corrupt line in an archived ledger is worth reporting,
not worth losing every other event to.

So the shared reader is the **tolerant** one, and the strictness is a thin wrapper the
report tool applies (`_load_jsonl` in `vultron/demo/report/timeline.py`): it raises
when `read_ledger_file` reports any unusable row. Put
the strictness in the shared reader instead and the measure layer cannot read a
damaged archive at all.
