---
title: Case Event History — Deriving CVD Events From a Case Ledger
status: active
kind: guidance
description: >
  Rules for changing the read-only layer that turns a case ledger into CVD event
  histories and per-vendor scores (`vultron/measure/`): what the derivation reads,
  which entry points a measure scores through, the ledger shapes the recorded test
  corpus does not cover, and where the shared JSONL walker lives.
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
  - docs/adr/0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md
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
alternative and rejected it are in ADR-0174 and ADR-0182, and the normative rules
are in `specs/case-event-history.yaml`. This note holds the traps and the layout
that neither carries.

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
- **Read the case's EM from the register the walk rebuilds.** The walk keeps each
  embargo register entry's status from the steps the ledger records (`derive_case`,
  `vultron/measure/history/reached.py`), and a measure that needs EM derives it from
  those statuses with `derive_em`, not from the stamped `CaseStatus.em`. Reason: EM
  is derived from the register, and the stamp is only a copy written when a case
  status is added (ADR-0122); in `rcv-embargo` the stamp reads `ACTIVE` while a
  proposal holds the register in `REVISE`.

## Score Through the Measure Layer's Entry Points

A measure scores each vendor's sequence against a baseline from the smallest model
that holds the desideratum's events: one vendor and the case's shared events, or two
vendors for a desideratum relating them (ADR-0182). Reason: a walk over the whole
case grows with the participant count, and its baselines change with that count, so
no table would serve every case. Do not build a whole-case walk, and do not key a
baseline on the number of participants. An incomplete sequence is scored through its
completions under the same walk (expected, best and worst), and a case reports
per-vendor scores with their unweighted median and spread (`score_case`).

Take the spread as the range (highest minus lowest), never a variance. Reason: the
vendors share P, X and A, so their scores are not a sample, and the spread reads as
evenness across vendors, not across users (ADR-0182).

Score through `vultron.measure.baselines`, never a second walk: its
`completion_probabilities(prefix)` weights each six-event completion from where the
case stands, and `frequency` serves any joint-model query. Reason: one walk keeps
the completions and the baselines under the same chance model (ADR-0182). Its joint
models obey only enforced rules — a SHOULD never constrains them, because the
desiderata measure exactly those preferences.

Read each vendor's desiderata values from where a case stands, and a step's expected
change, through `desiderata_values` and `expected_change`, never a whole-case walk:
they project the case onto each desideratum's own model, so a value from the start is
its baseline. Reason: a joint model's states multiply with each vendor added, so a
walk over a real case's vendors would not finish (#6449). The value depends on the
history as well as the state, because an ordering already met stays met, so pass a
`WalkPrefix`, not a bare `JointState`.

Score a move's advice on `expected_outcomes` and `outcome_change`, never on
`desiderata_values` alone or a hand-made mix of it with `scope_chances`: a desideratum
whose scope the case never enters counts as met (1), so the expected outcome is
P(not entered) × 1 + P(entered) × the conditional value. Reason: a case should not
lose points for not taking a worse path that had more points available, such as a
report never validated (user decision on #6457/#6490, recorded in #6488). The
conditional values stay as they are, `None` when the scope is unreachable, so a
value from the start is still the baseline.

Score a complete history with `vultron.measure.scoring.history_score`, never
`CVDmodel.score_hist`: it is the same `Σ (1 − f_d)` over the twelve original
desiderata, with exact baselines and no import of `vultron/core/case_states/`. A test
holds the two equal over the 70 histories.

## What the Recorded Corpus Does Not Cover

The committed canonical recordings under `ui/src/recordings/` are the test corpus:
each is the CASE_MANAGER's own copy of a real scenario run. Several requirements
rest on ledger data no recording holds, so each needs a hand-built fixture or it
passes with nothing exercising it (CEH-06-003, CEH-06-006):

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
  The object labels and the registry phrase render (`phrases.py`) moved with it, so
  `vultron-case-history` (`vultron/measure/history/cli.py`) words an event as the
  report does.
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
