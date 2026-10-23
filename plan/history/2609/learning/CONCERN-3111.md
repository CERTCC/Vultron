---
source: CONCERN-3111
timestamp: '2026-09-14T18:24:38.501599+00:00'
title: Consolidate the two ParticipantStatus writers outside the composed evaluator
type: learning
---

BTND-10-002 requires the rules governing a `ParticipantStatus` write to be composed
into one evaluator that every validating node calls. #3050 did that for the two BT
nodes on the case-participant emit path. This concern asked whether to consolidate
the writers that stayed outside it.

**Resolved**: 2026-09-14 — settled by ADR-0089; implementation is tracked in
issues #3204, #3206 and #3207.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3203>.
Spec: `specs/behavior-tree-node-design.yaml` BTND-10-002 (amended), BTND-10-004
through BTND-10-006. Notes: `notes/domain-validation.md`.

## What the concern got wrong, and why it matters

**The population was seven, not two.** The concern named
`CaseParticipant.append_rm_state()` and `_ReportPhaseRMTransition._guard_transition()`.
Scoping found seven writers, four of which the ratchet built to discover the
population could not see: `_get_or_create_accepted_status()`,
`_build_owner_initial_status()`, `_build_bootstrap_statuses()` — and the wire twin
`as_CaseParticipant.append_rm_state()`, which escapes for the opposite reason
(it names a predicate but builds `as_ParticipantStatus` from flat fields, so the
gate's construction half never matches, and it is in no declaration list).

**The ratchet's gate inverted the incentive.**
`test_no_undeclared_participant_status_validator` flagged a module only when it
*both* named a member predicate *and* constructed a dimension object. A writer that
validates nothing names no predicate, so it was never flagged. The detector caught
partial validators and missed wholly-unvalidated ones — the worse case. Durable
lesson: **when a structural ratchet keys on evidence of doing the right thing
badly, code that does nothing at all is outside its reach. Key on the write, not
on the check.**

**§2's conclusion was backwards.** The concern recorded the report phase as "a
deliberate separate lifecycle" with "no case participant". But
`_build_owner_initial_status()` reuses the marker's *id* as the participant's first
ladder rung, and `_get_or_create_accepted_status()` mutates the stored record in
place. That is one lifecycle at two stages, joined by id reuse — a mechanism no
requirement described. Asking *why* the earlier stage existed at all is what
surfaced it; the two named writers were symptoms of `ParticipantStatus` having two
jobs.

## The three objections, re-tested

The concern declined Design A on three grounds. All three changed under
investigation:

| Objection | Finding |
|---|---|
| "Unmeasured blast radius" on cross-machine entailments | **Zero on legal data** for the two RM-coupled rules, bounded by *reachability* rather than by running the suite. RM↔VF and RM↔D fire only when the F or D bit is set and RM ∉ {ACCEPTED, DEFERRED, CLOSED}; `VALID` is reachable only from `RECEIVED`/`INVALID`, `INVALID` only from `RECEIVED`, and a fix-ready `vf` requires having passed `ACCEPTED`, which RM never walks back from. VF↔D is RM-independent, so no RM value bounds it: it refuses `(vf, D)` and `(Vf, D)` at any RM state, which the D machine alone permits and which are corrupt regardless. Scope a reachability bound to the rules that actually read the dimension you bound on. |
| "The model cannot resolve the PXA baseline" | Only partly true. `resolve_participant_pxa_state()` treats the participant's *own* snapshots as authoritative and reads the case only as a fallback (#2264). Moot in the end: on an RM-only write `requested_pxa` is `None`, so the PXA rule is empty and the compound rule short-circuits on `current_vf is None`. |
| "Probable import cycle" | **Real and confirmed empirically** — `models/case_participant.py` → `states/participant_transitions.py` → `predicates/participants.py` → back. Breakable in two steps: the `CaseParticipant` import in `predicates/participants.py` is annotation-only and belongs under the `TYPE_CHECKING` block already in that file, but the module lacks `from __future__ import annotations` and its uses are unquoted function annotations, so the import must move *and* those annotations be quoted. Moot under ADR-0089, because the model stops validating. |

The general shape: an objection recorded as a reason not to act deserves
re-testing when it is finally acted on. Two of these three had decayed, and the
one that held was irrelevant to the design that won.

## Why neither Design A nor Design B won as written

The concern framed the choice as "route the model method through the evaluator"
versus "move its callers to the BT write path". Both accept the premise that
pre-case RM state is a `ParticipantStatus`. Dropping that premise dissolved the
question: `VultronReportCaseLink` already exists for the pre-case window
(ADR-0041), so relocating the state there leaves `ParticipantStatus` ladder-only,
gives the writer a case in every path, and needs no fourth ADR-0087 disposition.
The resolution is net subtractive — three helpers, one record shape, six nodes,
two model mutators and one dead module go away.

A proto-case (create a real case at report receipt, hand `CASE_MANAGER` to a
CaseActor later) was proposed and rejected: it is ADR-0015's model, which ADR-0041
supersedes for precisely this reason, and the handoff step it depends on is on
ADR-0041's "what is removed" list. Worth knowing that the archived ADR directory
holds the answer to a question that looks new.

## Adjacent findings

- **`vultron/core/use_cases/received/case/validate.py` is dead code.** All three
  classes have no production callers. The semantic registry routes the
  similarly-named `CloseCaseReceivedUseCase` from `lifecycle.py`, which is almost
  certainly why they survived; their docstrings claim a caller that now runs a BT
  instead. Near-identical names are a dead-code preservative.
- **`update_participant_rm_state()` was an unseen BT-audit-trail bypass.** It
  calls `dl.save()`, so reaching it from a use case's `execute()` persisted outside
  the tree — invisible because `test_no_dl_mutations_in_execute.py` walks
  `execute()` bodies without following into helpers. Same blind-spot shape as the
  validation ratchet: the detector's reach stopped one call short.
- **Three ways to do one thing, not two.** `CreateParticipantStatusNode` was
  reached as a tree child at 2 sites and constructed-and-ticked inside another
  node's `update()` at 5, while 6 further nodes bypassed it entirely. The nested
  form skips `setup()` and the tick cycle, and two of those sites (`deploy_fix.py`,
  `develop_fix.py`) wrapped it in `try/except`. A "two writers" concern can hide a
  third mechanism that is the majority pattern.
- **`_set_accepted_status` exists twice**, byte-identical, on `ReporterParticipant`
  and `FinderReporterParticipant` (ARCH-15-004, CS-22-001).
- **`docs/adr/archived/README.md` claimed the archive was empty** while ADR-0015
  sat in it — a restated-contents staleness of the kind MS-16-001 forbids.
- **ADR number race caught before merge.** PR #3180 already claimed 0088, so this
  became 0089 — the `notes/git-workflow-pitfalls.md` pitfall, live.
