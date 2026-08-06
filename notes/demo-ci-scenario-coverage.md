---
title: Demo CI Scenario Coverage Matrix and Minimum PR Validation Set
status: active
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
---

# Demo CI: Scenario Coverage Matrix and Minimum PR Validation Set

Spec: DEMOCI-06. Analysis performed as part of ISSUE-1996.

## Coverage Matrix

The table below maps each of the 8 demo scenarios to the distinct protocol
event types it exercises. Event types are those recorded as `event_type` in
`CaseLedgerEntry` and validated by Invariant 5
(`test_invariant_5_expected_event_types_present`) in each scenario's
`test/ci/invariants/test_XXX_invariants.py` file.

| Scenario | validate_report | add_participant_status_to_participant | close_case | add_note_to_case | invite_actor_to_case | offer_case_participant | accept_invite_actor_to_case | accept_actor_recommendation |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| fv                | ✓ | ✓ | ✓ | ✓ |   |   |   |   |
| fvv               | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   |
| fvcv-extension    | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| fvcv-handoff      | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   |
| fccv-extension    | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| fccv-handoff      | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   |
| fcvcv             | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| fcv               | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   |

**Notes:**

- The four universal types (`validate_report`, `add_participant_status_to_participant`,
  `close_case`, `add_note_to_case`) appear in every scenario (DEMOMA-16-001).
- Ownership transfer (`attributed_to` mutation via `AcceptCaseOwnershipTransferNode`)
  is exercised by `fvcv-handoff` and `fccv-handoff` but does **not** emit a
  `CaseLedgerEntry` with a named `event_type`. It is therefore not observable via
  Invariant 5 — instead it is verified by `demo_check` assertions in the scenario
  script itself. The ownership-transfer protocol path is covered by `fvcv-handoff`
  in the minimum PR set.
- `accept_actor_recommendation` is emitted by `AcceptActorRecommendationNode`
  (`vultron/core/behaviors/case/nodes/suggest_actor/emit.py:283`) when an actor
  approves a suggested participant. It fires only in scenarios that include the
  ADR-0026 suggest-actor flow: `fvcv-extension`, `fccv-extension`, and `fcvcv`.
- `add_case_participant` is emitted by `AcceptInviteNode`
  (`vultron/core/behaviors/case/nodes/accept_invite.py:181`) on the CaseActor
  received-side when processing Accept(Invite). This event records the internal
  participant-list bookkeeping rather than a protocol-visible coordination action.
  It fires in every scenario with invite/accept flows (7 of 8) but is intentionally
  excluded from `_EXPECTED_EVENT_TYPES` lists: it is a `CaseActor`-internal
  ledger entry, not a coordination event that invariant checks should mandate.
- `fccv-extension` spec entry DEMOMA-16-010 was added as part of ISSUE-1996;
  the test constant was already correct.
- `fvv`, `fvcv-extension`, and `fcv` were missing `accept_invite_actor_to_case`
  from their `_EXPECTED_EVENT_TYPES` lists; corrected as part of ISSUE-1996 (AC-2).
- `fcvcv`, `fvcv-extension`, and `fccv-extension` were missing
  `accept_actor_recommendation`; corrected as part of ISSUE-1996 (AC-2 follow-up).

## AC-2 Corrections Applied

| File | Added event type |
|---|---|
| `test/ci/invariants/test_fvv_invariants.py` | `accept_invite_actor_to_case` |
| `test/ci/invariants/test_fcv_invariants.py` | `accept_invite_actor_to_case` |
| `test/ci/invariants/test_fvcv_extension_invariants.py` | `accept_invite_actor_to_case` |
| `test/ci/invariants/test_fcvcv_invariants.py` | `accept_actor_recommendation` |
| `test/ci/invariants/test_fvcv_extension_invariants.py` | `accept_actor_recommendation` |
| `test/ci/invariants/test_fccv_extension_invariants.py` | `accept_actor_recommendation` |

Corresponding DEMOMA-16 spec entries updated: 16-003, 16-004, 16-007.
New spec entry DEMOMA-16-010 added for `fccv-extension`.

## Coverage Scope: What the Matrix Covers and Why

The matrix above is scoped to `CaseLedgerEntry.event_type` values that represent
distinct **coordination protocol phases** — actions a participant takes that
advance the CVD protocol state and are recorded in the replicated case ledger.

### Dimensions in scope (observable via Invariant 5)

| Column | Protocol phase |
|---|---|
| `validate_report` | Report validation (RM state: received → valid) |
| `add_participant_status_to_participant` | Participant status tracking |
| `close_case` | Case closure |
| `add_note_to_case` | Case note / information sharing |
| `invite_actor_to_case` | Actor invitation |
| `offer_case_participant` | Suggest-actor flow (ADR-0026) |
| `accept_invite_actor_to_case` | Invitation acceptance |
| `accept_actor_recommendation` | Recommendation approval (ADR-0026) |

### Dimensions covered outside Invariant 5

| Dimension | Covered by | How verified |
|---|---|---|
| Ownership transfer | `fvcv-handoff`, `fccv-handoff` | `demo_check` assertions in scenario script (not a ledger event_type) |
| CVD role variation | All 8 scenarios | Scenario scripts define actor roles (deployer/vendor-only/coordinator) |
| Fix-ready / fix-deployed lifecycle (VFd vs VFD) | All scenarios run to RM closed | Invariant 7 (`test_invariant_7_log_terminates_all_rm_closed`) |
| Multi-vendor vs single-vendor fix paths | `fvv`, `fcvcv`, `fvcv-extension` (multiple vendors) vs `fv`, `fcv` (single) | Scenario composition; covered by minimum set via `fcvcv` |
| Embargo lifecycle phases | Scenarios with Coordinator actors | `demo_check` + EM state assertions in scenario scripts |

### Why the minimum set is sufficient

The 3-scenario minimum set (`fv`, `fvcv-handoff`, `fcvcv`) covers all 8
`event_type` columns and the ownership-transfer path. The additional dimensions
(CVD role variation, multi-vendor fix paths, embargo phases) are either:

- exercised by multiple minimum-set scenarios (multi-vendor: `fcvcv`), or
- verified by separate invariants that do not require additional scenarios (RM
  closure: Invariant 7), or
- scenario-script `demo_check` assertions that run with the scenario regardless
  of which CI tier it lands in.

The 5 full-suite-only scenarios add regression depth but not breadth relative to
the minimum set's event-type and protocol-path coverage.

## Minimum PR Validation Set (DEMOCI-06-002)

**Set: `fv`, `fvcv-handoff`, `fcvcv`**

| Scenario | Covered by minimum set | Rationale |
|---|:---:|---|
| fv | ✓ (member) | 2-actor baseline; covers all 4 universal event types with no invitation phases |
| fvcv-handoff | ✓ (member) | Adds `invite_actor_to_case` + `accept_invite_actor_to_case` + ownership-transfer protocol path |
| fcvcv | ✓ (member) | Adds `offer_case_participant` + `accept_actor_recommendation` + ≥3-actor invite/accept chains |
| fvv | covered by fvcv-handoff | Same invite+accept coverage; no additional phases |
| fvcv-extension | covered by fcvcv | Same offer+invite+accept coverage; no additional phases |
| fccv-extension | covered by fcvcv | Same offer+invite+accept coverage; no additional phases |
| fccv-handoff | covered by fvcv-handoff | Same invite+accept+ownership-transfer; no additional phases |
| fcv | covered by fvcv-handoff | Same invite+accept coverage; no additional phases |

### Coverage proof

The minimum set of 3 scenarios covers all 8 distinct event types:

| Event type | Covered by |
|---|---|
| validate_report | fv |
| add_participant_status_to_participant | fv |
| close_case | fv |
| add_note_to_case | fv |
| invite_actor_to_case | fvcv-handoff |
| accept_invite_actor_to_case | fvcv-handoff |
| offer_case_participant | fcvcv |
| accept_actor_recommendation | fcvcv |

The 5 remaining scenarios (`fvv`, `fvcv-extension`, `fccv-extension`,
`fccv-handoff`, `fcv`) produce no event type not already covered by the
minimum set. They run only on push to `main` (DEMOCI-06-003) to provide
regression coverage without increasing PR wall-clock cost.

## Workflow Implementation (DEMOCI-06-003)

`.github/workflows/demo-integration.yml` was updated to:

1. Add a `push: branches: ["main"]` trigger (implements DEMOCI-05-001 and
   DEMOCI-06-003, which were previously unimplemented).
2. Mark `fv`, `fvcv-handoff`, and `fcvcv` as `full_suite_only: false` — they
   run on every `pull_request` event.
3. Mark the remaining 5 scenarios as `full_suite_only: true` — they run only
   on `push` to main and `workflow_dispatch`.
4. Add a job-level `if:` condition that skips `full_suite_only: true` entries
   on `pull_request` events. Both `demo` and `invariant-harness` jobs carry the
   same gate condition so the artifact/download pairing stays consistent.

See ADR-0052 for the accepted barrier + concurrency group design that DEMOCI-06
finalises.
