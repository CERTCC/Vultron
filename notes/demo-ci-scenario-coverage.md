---
title: "Demo CI: Scenario Coverage Matrix and Minimum PR Validation Set"
status: active
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
related_notes:
  - notes/ci-workflow-authoring.md
  - notes/demo-scenario-registry.md
---

# Demo CI: Scenario Coverage Matrix and Minimum PR Validation Set

Spec: DEMOCI-06. Analysis performed as part of ISSUE-1996; updated for
`fcv-reject` (IDEA-1218).

## Coverage Matrix

The table below maps every demo scenario to the distinct protocol event types it
exercises. Event types are those recorded as `event_type` in `CaseLedgerEntry`
and validated by Invariant 5
(`test_invariant_5_expected_event_types_present`) in each scenario's
`test/ci/invariants/test_XXX_invariants.py` file.

The `Scenario` column is the scenario registry's, in the registry's name order,
and is checked against it (DEMOCI-11-007). The event-type ticks are checked too,
against each scenario's `_XXX_EXPECTED_EVENT_TYPES` harness constant — the same
constant Invariant 5 asserts against, so a tick that disagrees describes a
scenario CI does not run (MS-16-002, ISSUE-3505). Adding a scenario, or adding an
event type to a harness constant, therefore fails this check until the table
follows — see [demo-scenario-registry.md](demo-scenario-registry.md) § "The
generate-vs-check split".

| Scenario | validate_report | add_participant_status_to_participant | close_case | add_note_to_case | engage_case | invite_actor_to_case | offer_case_participant | accept_invite_actor_to_case | accept_actor_recommendation | accept_case_ownership_transfer | reject_invite_actor_to_case |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| fccv-extension    | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |
| fccv-handoff      | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   | ✓ |   |
| fcv               | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   |   |   |
| fcv-reject        | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |   |   | ✓ |
| fcvcv             | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |
| fv                | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |   |   |   |   |
| fvcv-extension    | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |
| fvcv-handoff      | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   | ✓ |   |
| fvv               | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   |   |   |

**Notes:**

- The universal types (DEMOMA-16-001) appear in every scenario.
- `engage_case` is universal because emission lives in the shared demo helper
  layer, not at scenario call sites: `run_direct_path_rm_triage()` calls
  `receiver_engages_case()` for the direct receiver (every multi-actor
  scenario), `run_invite_path_rm_triage()` calls it again for the invited
  participant (every scenario with an invite path, CM-11-002), and
  `fv_demo.py` calls it via
  `vendor_engages_case()`. It was promoted from a `fvcv-handoff`-only entry to
  the fifth universal type in ISSUE-2266; see
  `notes/demo-ci-invariants.md` § "`engage_case` is universal, not
  scenario-specific".
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
- `reject_invite_actor_to_case` is emitted by `RejectInviteActorToCaseReceivedUseCase`
  on the CaseActor when an invitee sends `Reject(Invite(actor, case))` — an
  **invitation-layer** rejection (not an RM-state RI/RC message). It fires only in
  `fcv-reject` (IDEA-1218): the Vendor receives the case invitation and sends
  `Reject(Invite(actor, case))` to decline it, which triggers
  `RejectInviteActorToCaseReceivedUseCase` on the CaseActor. Because the Vendor
  rejects rather than accepts, `accept_invite_actor_to_case` does NOT appear in
  this scenario. No other current scenario exercises this ledger entry.
  **Invariant 15 note**: because the Vendor never participates, no actor advances
  the VFD state machine and the `VFd` CS state (vf_state=VF, d_state=d) is structurally unreachable.
  However, `check_cs_state_transitions_observed()` in
  `test/ci/invariants/common.py` no longer accepts a `check_fix_ready` parameter
  — the VFd assertion is unconditional as of PR #2152. `test_invariant_15` in
  `test_fcv_reject_invariants.py` passes without `check_fix_ready=False` because
  `fcv-reject` CI produces a VFd observation in practice. When copy-pasting
  Invariant 15 from another harness, do not pass `check_fix_ready=False` — that
  parameter no longer exists (DEMOCI-06-001, ISSUE-2121, PR #2152).
- `add_case_participant` is emitted by `AcceptInviteNode`
  (`vultron/core/behaviors/case/nodes/accept_invite.py:181`) on the CaseActor
  received-side when processing Accept(Invite). This event records the internal
  participant-list bookkeeping rather than a protocol-visible coordination action.
  It fires in every scenario with invite/accept flows but is intentionally
  excluded from `_EXPECTED_EVENT_TYPES` lists: it is a `CaseActor`-internal
  ledger entry, not a coordination event that invariant checks should mandate.
- `fccv-extension` spec entry DEMOMA-16-010 was added as part of ISSUE-1996;
  the test constant was already correct.
- `fvv`, `fvcv-extension`, and `fcv` were missing `accept_invite_actor_to_case`
  from their `_EXPECTED_EVENT_TYPES` lists; corrected as part of ISSUE-1996 (AC-2).
- `fcvcv`, `fvcv-extension`, and `fccv-extension` were missing
  `accept_actor_recommendation`; corrected as part of ISSUE-1996 (AC-2 follow-up).
- `fcv-reject` (DEMOMA-16-011) was added as part of IDEA-1218 planning.

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
| `engage_case` | RM engagement (RM state: valid → accepted) |
| `invite_actor_to_case` | Actor invitation |
| `offer_case_participant` | Suggest-actor flow (ADR-0026) |
| `accept_invite_actor_to_case` | Invitation acceptance |
| `accept_actor_recommendation` | Recommendation approval (ADR-0026) |
| `reject_invite_actor_to_case` | Invitation-layer rejection (`Reject(Invite(actor, case))`) |

### Dimensions covered outside Invariant 5

| Dimension | Covered by | How verified |
|---|---|---|
| Ownership transfer | `fvcv-handoff`, `fccv-handoff` | `demo_check` assertions in scenario script (not a ledger event_type) |
| CVD role variation | Every scenario | Scenario scripts define actor roles (deployer/vendor-only/coordinator) |
| Fix-ready / fix-deployed lifecycle (VFd vs VFD) | All scenarios run to RM closed | Invariant 7 (`test_invariant_7_log_terminates_all_rm_closed`) |
| Multi-vendor vs single-vendor fix paths | `fvv`, `fcvcv`, `fvcv-extension` (multiple vendors) vs `fv`, `fcv` (single) | Scenario composition; covered by minimum set via `fcvcv` |
| Embargo lifecycle phases | Scenarios with Coordinator actors | `demo_check` + EM state assertions in scenario scripts |

### Why the minimum set is sufficient

The minimum set (`fv`, `fvcv-handoff`, `fcvcv`, `fcv-reject`) covers every
`event_type` column and the ownership-transfer path. The additional
dimensions (CVD role variation, multi-vendor fix paths, embargo phases) are
either:

- exercised by multiple minimum-set scenarios (multi-vendor: `fcvcv`), or
- verified by separate invariants that do not require additional scenarios (RM
  closure: Invariant 7), or
- scenario-script `demo_check` assertions that run with the scenario regardless
  of which CI tier it lands in.

The full-suite-only scenarios add regression depth but not breadth relative to
the minimum set's event-type and protocol-path coverage. (`fcv-reject` is a
minimum-set member because it cannot be covered by any other scenario:
`reject_invite_actor_to_case` is unique to the invitation-rejection path.)

## Minimum PR Validation Set (DEMOCI-06-002)

**The set is the rows marked `✓ (member)` below**, and that column is checked
against each scenario's `in_pr_set` decorator field. The membership is
deliberately *not* also restated here in prose: a second copy would drift from
the column beside it and no test could falsify the sentence (MS-16-002).

Rows are in the registry's name order, checked against it, and PR-set membership
reads off the `Covered by minimum set` column rather than off position — see
[demo-scenario-registry.md](demo-scenario-registry.md) § "Name order is the
canonical order, everywhere".

| Scenario | Covered by minimum set | Rationale |
|---|:---:|---|
| fccv-extension | covered by fcvcv | Same offer+invite+accept coverage; no additional phases |
| fccv-handoff | covered by fvcv-handoff | Same invite+accept+ownership-transfer; no additional phases |
| fcv | covered by fvcv-handoff | Same invite+accept coverage; no additional phases |
| fcv-reject | ✓ (member) | Adds `reject_invite_actor_to_case` — the only scenario where the Vendor sends `Reject(Invite(actor, case))` (invitation-layer rejection) |
| fcvcv | ✓ (member) | Adds `offer_case_participant` + `accept_actor_recommendation` + ≥3-actor invite/accept chains |
| fv | ✓ (member) | 2-actor baseline; covers all universal event types (DEMOMA-16-001) with no invitation phases |
| fvcv-extension | covered by fcvcv | Same offer+invite+accept coverage; no additional phases |
| fvcv-handoff | ✓ (member) | Adds `invite_actor_to_case` + `accept_invite_actor_to_case` + ownership-transfer protocol path |
| fvv | covered by fvcv-handoff | Same invite+accept coverage; no additional phases |

### Coverage proof

The minimum set covers every distinct event type:

| Event type | Covered by |
|---|---|
| validate_report | fv |
| add_participant_status_to_participant | fv |
| close_case | fv |
| add_note_to_case | fv |
| engage_case | fv |
| invite_actor_to_case | fvcv-handoff |
| accept_invite_actor_to_case | fvcv-handoff |
| offer_case_participant | fcvcv |
| accept_actor_recommendation | fcvcv |
| accept_case_ownership_transfer | fvcv-handoff |
| reject_invite_actor_to_case | fcv-reject |

Every non-member row above — the scenarios whose `Covered by minimum set` cell
names a covering member rather than `✓ (member)` — produces no event type the
minimum set does not already cover. They run only on push to `main`
(DEMOCI-06-003) to provide regression coverage without increasing PR wall-clock
cost. The membership is not re-listed here for the same reason it is not restated
above the table: the column is the answer, and it is the copy a test can falsify
(MS-16-002).

## Workflow Implementation (DEMOCI-06-003)

`.github/workflows/demo-integration.yml` selects the matrix for the current
event:

- A `push: branches: ["main"]` trigger runs the whole suite (DEMOCI-05-001,
  DEMOCI-06-003); `workflow_dispatch` does the same for any ref.
- On `pull_request`, the `scenarios` job drops every `full_suite_only` entry,
  leaving the minimum PR validation set (DEMOCI-06-002). `full_suite_only` is
  the inverse of each scenario's `in_pr_set` decorator field and reaches the
  workflow through the generated `.github/demo-scenarios.json` (DEMOCI-11-004).
- The filter lives in the `scenarios` job rather than in a job-level `if:` on a
  matrix field, because job `if:` is evaluated before matrix expansion — see
  DEMOCI-06-004 and `notes/ci-workflow-authoring.md`.

See ADR-0052 for the accepted barrier + concurrency group design that DEMOCI-06
finalises.

### Change history

Statements here record past states and are exempt from the no-restated-count
rule (DEMOCI-11-008), which is why the exemption is keyed on this heading.

- PR #2030 added the `push: branches: ["main"]` trigger and marked `fv`,
  `fvcv-handoff` and `fcvcv` as `full_suite_only: false`, leaving the rest
  full-suite-only.
- PR #2084 (IDEA-1218) implemented `fcv-reject` and added it as a matrix entry
  with `full_suite_only: false` (DEMOCI-03-002). Full-suite scenario list
  updated from 8 to 9 scenarios.
- PR #3464 (ISSUE-3450) made the matrix a generated projection of the scenario
  registry, so the entries are no longer hand-maintained here or in the
  workflow (ADR-0098).

## RM State-Transition Path Coverage

The event-type matrix (above) captures which protocol coordination phases each
scenario exercises, but it does not distinguish *which RM state-to-state paths*
are taken within those phases. Because `validate_report` is emitted on both the
linear R → V path and the non-linear R → I → V path, and `add_participant_status_to_participant`
is emitted on both A → D and D → A, the invariant harness alone cannot verify
non-linear RM paths. Once implemented (#2050), these will be validated by
`demo_check` assertions in the scenario scripts themselves.

The table below maps the distinct RM state-transition paths to the scenarios
planned to exercise them (implementation tracked in #2050). "Linear" paths
are those shown in a typical happy-path
trace; "non-linear" paths are detours the RM state machine permits but that
do not appear in any scenario unless explicitly scripted.

| RM transition path | Type | Planned scenario (#2050) |
|---|---|---|
| S → R (report received) | linear | all scenarios |
| R → V (report valid) | linear | all scenarios |
| V → A (report accepted / engaged) | linear | all scenarios |
| A → C (case closed) | linear | all scenarios |
| R → I (report invalid) | non-linear | `fvcv-handoff` (Var A, planned) |
| I → V (re-validated after rejection) | non-linear | `fvcv-handoff` (Var A, planned) |
| A → D (report deferred) | non-linear | `fcvcv` (Var B, planned) |
| D → A (resumed after deferral) | non-linear | `fcvcv` (Var B, planned) |
| I → C (closed from invalid) | non-linear | not yet exercised by any scenario |
| V → D (deferred without accepting) | non-linear | not yet exercised by any scenario |

**Notes:**

- Variation A (`fvcv-handoff`, R → I → V, planned in #2050): Vendor1 will
  call `invalidate-report` (RI), then the Finder will post a clarifying case
  note and Vendor1 will call `validate-report` (RV), advancing to V before
  engaging. A `demo_check` assertion will verify Vendor1's RM state is
  INVALID before re-validation and VALID immediately after.
- Variation B (`fcvcv`, A → D → A, planned in #2050): V1 will call
  `engage-case` (RA), then `defer-case` (RD), then `engage-case` again
  (RV → accepted). A `demo_check` assertion will verify the DEFERRED state
  before the second `engage-case` call. The RM state machine already supports
  `ACCEPT: DEFERRED → ACCEPTED` (rm.py line 145); no new BT nodes are needed.
- The `I → C` and `V → D` paths are valid per the RM state machine but are
  not exercised by any current scenario. They are candidates for a future
  scenario or scenario extension.

Source: ISSUE-1221 planning (2026-08-06).
