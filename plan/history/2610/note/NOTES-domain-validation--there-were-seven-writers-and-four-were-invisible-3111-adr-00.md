---
source: NOTES-domain-validation--there-were-seven-writers-and-four-were-invisible-3111-adr-00
timestamp: '2026-10-02T16:28:29.386972+00:00'
title: There were seven writers, and four were invisible (#3111, ADR-0089)
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered + redundant + closed — #3111 closed; ADR-0089 records the seven-writer finding and the construction-only detector gate; the listed unvalidated writers are gone
**Superseded by:** ADR-0089; test/architecture/test_participant_status_validation.py

---

## There were seven writers, and four were invisible (#3111, ADR-0089)

CONCERN-3111 recorded two writers outside the evaluator. Scoping it found seven
that append a ladder rung or write the marker record. The four the ratchet could
not see are the important part:

| Writer | Validates | Ratchet sees it? |
|---|---|---|
| `CreateParticipantStatusNode` | the whole rule set | yes |
| `CaseParticipant.append_rm_state()` | RM adjacency only | declared |
| `_ReportPhaseRMTransition._write_latch()` | RM adjacency only | declared |
| `as_CaseParticipant.append_rm_state()` | RM adjacency only | **no** — wire twin, see below |
| `common.py::_get_or_create_accepted_status()` | **nothing** | **no** |
| `owner.py::_build_owner_initial_status()` | **nothing** | **no** |
| `case_proposal_received_tree.py::_build_bootstrap_statuses()` | **nothing** | **no** |

Count the writers, not the `ParticipantStatus(...)` calls: the seven above
exclude the constructor-seeding validators
(`CaseParticipant._init_participant_status_if_empty`, and
`_set_accepted_status` on `ReporterParticipant` and `FinderReporterParticipant`
— see the seeding-validator pitfall below), the demo seeder in
`demo/helpers/seeding.py`, and the wire→core extractor in
`wire/as2/extractor/_builders.py`. Those construct a status but do not advance a
participant's ladder.

**The detector's gate was the hole.**
`test_no_undeclared_participant_status_validator` flagged a module only when it
*both* named a member predicate *and* constructed a dimension object. A writer
that validates nothing names no predicate, so it was never flagged — the
detector caught partial validators and missed wholly-unvalidated ones. Under
ADR-0089 the gate is construction alone: **any** module that builds a participant
dimension is in the population. Validating less no longer buys invisibility.

**The wire twin escapes both gates, and needs its own trigger.**
`as_CaseParticipant.append_rm_state()` is in neither `_VALIDATING_NODE_MODULES`
nor `_DECLARED_EXCLUSIONS` — the ratchet has no reference to `vultron/wire/` at
all. It names `is_valid_rm_transition`, so the *old* gate's predicate half
matches, but it builds `as_ParticipantStatus` from flat fields (`rm_state=`)
rather than a dimension object, so the construction half never fires. Widening
the gate to construction alone does not reach it either, for the same reason. The
wire projection's construction shape has to be added to the trigger set
explicitly, or "every writer is visible" stays false for the wire layer.

The general lesson: when a structural ratchet keys on evidence of *doing the
right thing badly*, the code that does nothing at all is outside its reach. Key
on the write, not on the check.
