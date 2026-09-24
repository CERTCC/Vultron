---
title: "ADR-0089 AC-7 says the ratchet exclusion list ends at 'exactly two entries', but the ADR's own prose calls the reader/projection over-catch permanent — the literal AC contradicts its governing ADR"
type: learning
timestamp: "2026-09-16T00:00:00Z"
source: ISSUE-3207
signal: spec-contradiction
---

Issue #3207 AC-7 reads: "the ratchet exclusion list ends holding exactly two
entries, both deliberate — `status/nodes/_adjudication.py` (receive path,
ADR-0061) and `sync/nodes/participant_status_effect.py` (replica-apply,
RSH-05-021)."

`test/architecture/test_participant_status_validation.py`'s
`test_no_undeclared_participant_status_validator` gate fires on **any** module
under `vultron/core/behaviors/` that constructs a participant dimension
(`RmDimension`/`VfDimension`/`DDimension`/`PxaDimension`). By construction it
also catches modules that never *write* a `ParticipantStatus` — read-side
carry-forward (`common.py`), guard predicates (`deploy_fix.py`,
`develop_fix_conditions.py`), and `CaseStatus` writers whose dimension happens
to be `PxaDimension` (`case_status.py`, `cs_dimension_filter.py`). ADR-0089's
own Decision-Outcome prose says exactly this and calls those declarations
**permanent**:

> "Those declarations are the price of a gate that cannot be escaped by
> validating less; they are permanent … If the over-catch proves too noisy to
> live with, the alternative is a narrower gate that keys on assignment into
> `participant_statuses` — but that reintroduces a structural property a writer
> can dodge, which is the failure mode this section exists to remove."

So the two statements cannot both be literally true. Ending at **exactly two
entries** requires narrowing the gate to real writers — which is the very
alternative ADR-0089 evaluated and rejected. The reconciling reading is that
ADR-0089 means **two *writer* exclusions**, alongside a permanent non-writer
over-catch; the ADR's "ending at two writer exclusions" phrase (one paragraph
later) supports that, but AC-7 dropped the word "writer" and reads as a
count of the whole list.

This was resolved by adjudication (interpret AC-7 as two *writer* exclusions;
keep the five non-writer entries with a header comment distinguishing the two
kinds). But the contradiction still lives in **both** the issue AC text and
ADR-0089's Decision Outcome, so the next reader of either — or the next author
of a similar "drive the ratchet list down to N" AC — will hit it again.

**How to apply.** When a ratchet's gate is deliberately over-broad (keys on a
structural signal a writer cannot dodge), any acceptance criterion about "how
many exclusions remain" MUST say *which kind* it counts — writer exclusions vs.
the permanent over-catch — or the literal number contradicts the design that
made the gate over-broad on purpose. Candidate doc work: revise ADR-0089 in
place to say "two **writer** exclusions plus the permanent non-writer
over-catch" wherever it currently says "two entries", and reword future ACs
the same way.

Related: the same shape as the CLP-14/CLP-15 and MV-01-006 lessons —
[[20260903-2824-clp14-15-do-not-name-their-timestamp]],
[[20260914-3217-mv-01-006-unrecognized-type-names-two-registries]] — a
requirement that constrains one member of a population without naming which.

**Promoted**: 2026-09-17 — captured in `docs/adr/0089-one-participant-status-writer.md` (Validation section) and `notes/spec-authoring-rules.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3328>
