---
title: "Demo CI: Scenario Coverage Matrix and Minimum PR Validation Set"
status: active
kind: guidance
description: >
  Which protocol event types and RM paths each demo scenario exercises, why the
  DEMOCI-06-002 minimum PR set is sufficient, and how the workflow selects it.
  The scenario tables are ratcheted against the registry and the harness
  constants (DEMOCI-11-007).
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
  - specs/case-management.yaml
  - specs/rm-behavior.yaml
related_notes:
  - notes/ci-workflow-authoring.md
  - notes/demo-scenario-registry.md
  - notes/demo-ci-invariants.md
  - notes/demo-ci-diagnostics.md
  - notes/case-joining.md
  - notes/cvd-recipe-injects.md
---

# Demo CI: Scenario Coverage Matrix and Minimum PR Validation Set

Spec: DEMOCI-06. Every scenario table here is checked in place against the
scenario registry (row set and name order) and against each scenario's
`_XXX_EXPECTED_EVENT_TYPES` harness constant, which is what Invariant 5 asserts
(DEMOCI-11-007, MS-16-002). Adding a scenario, or an event type to a harness
constant, fails the check until the tables follow — see
[demo-scenario-registry.md](demo-scenario-registry.md) § "The generate-vs-check
split".

## Coverage Matrix

Columns are `CaseLedgerEntry.event_type` values, each a distinct coordination
protocol phase recorded in the replicated ledger.

| Scenario | validate_report | add_participant_status_to_participant | close_case | add_note_to_case | engage_case | invite_actor_to_case | offer_case_participant | accept_invite_actor_to_case | accept_actor_recommendation | accept_case_ownership_transfer | reject_invite_actor_to_case | invite_to_embargo_on_case | accept_invite_to_embargo_on_case | activate_embargo_on_case | remove_embargo_event_from_case |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| fccv-extension    | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |   |   |   |   |
| fccv-handoff      | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   | ✓ |   |   |   |   |   |
| fcv               | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   |   |   |   |   |   |   |
| fcv-reject        | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |   |   | ✓ |   |   |   |   |
| fcvcv             | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |   |   |   |   |
| fv                | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |   |   |   |   |   |   |   |   |
| fvcv-extension    | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |   |   |   |   |
| fvcv-handoff      | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   | ✓ |   |   |   |   |   |
| fvv               | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   |   |   |   |   |   |   |
| rcv-embargo       | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   |   |   | ✓ | ✓ | ✓ | ✓ |
| rcvv-embargo      | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   | ✓ |   |   |   | ✓ | ✓ | ✓ | ✓ |

- The first five columns are the universal types (DEMOMA-16-001). `engage_case`
  is emitted from the shared helpers, not scenario call sites — see
  `notes/demo-ci-invariants.md` § "`engage_case` is universal, not
  scenario-specific".
- `offer_case_participant` and `accept_actor_recommendation` come only from the
  suggest-actor flow (ADR-0026).
- `reject_invite_actor_to_case` comes only from `fcv-reject`: the Vendor sends
  `Reject(Invite(actor, stub))`, so `accept_invite_actor_to_case` is absent. The
  stub Reject is an RM message that closes the Vendor's inert record, `R → C`
  (ADR-0114, CM-11-007).
- No scenario lists `add_case_participant`: replicas seat a joiner from the
  `accept_invite_actor_to_case` entry and the CASE_MANAGER sends no
  `Add(CaseParticipant)` (CM-31-012, ADR-0116).

## What the Matrix Does Not Cover

Some dimensions are not ledger event types, so Invariant 5 cannot see them:

| Dimension | Covered by | How verified |
|---|---|---|
| CVD role variation | Every scenario | Actor roles in the scenario scripts |
| RM closure for every participant | Every scenario | Invariant 7 (`test_invariant_7_log_terminates_all_rm_closed`) |
| Multi-vendor vs single-vendor fix paths | `fvv`, `fcvcv`, `fvcv-extension` vs `fv`, `fcv` | Scenario composition; `fcvcv` is in the minimum set |
| Embargo EM states | Scenarios with an embargo | `demo_check` and EM state assertions in the scenario scripts |
| Non-linear RM paths | See "RM State-Transition Path Coverage" | `demo_check` assertions in the scenario scripts |

## Minimum PR Validation Set (DEMOCI-06-002)

**The set is the rows marked `✓ (member)` below.** That column is checked against
each scenario's `in_pr_set` decorator field, so the membership is not restated in
prose (MS-16-002). Rows follow the registry's name order — see
[demo-scenario-registry.md](demo-scenario-registry.md) § "Name order is the
canonical order, everywhere".

| Scenario | Covered by minimum set | Rationale |
|---|:---:|---|
| fccv-extension | covered by fcvcv | Same offer+invite+accept coverage; no additional phases |
| fccv-handoff | covered by fvcv-handoff | Same invite+accept+ownership-transfer; no additional phases |
| fcv | covered by fvcv-handoff | Same invite+accept coverage; no additional phases |
| fcv-reject | ✓ (member) | Adds `reject_invite_actor_to_case` — the only scenario where the Vendor sends `Reject(Invite(actor, stub))` (declines the stub Invite) |
| fcvcv | ✓ (member) | Adds `offer_case_participant` + `accept_actor_recommendation` + ≥3-actor invite/accept chains |
| fv | ✓ (member) | 2-actor baseline; covers all universal event types (DEMOMA-16-001) with no invitation phases |
| fvcv-extension | covered by fcvcv | Same offer+invite+accept coverage; no additional phases |
| fvcv-handoff | ✓ (member) | Adds `invite_actor_to_case` + `accept_invite_actor_to_case` + ownership-transfer protocol path |
| fvv | covered by fvcv-handoff | Same invite+accept coverage; no additional phases |
| rcv-embargo | ✓ (member) | Adds `invite_to_embargo_on_case` + `accept_invite_to_embargo_on_case` + `activate_embargo_on_case` + `remove_embargo_event_from_case` — the only scenario that proposes, activates and terminates an embargo |
| rcvv-embargo | ✓ (member) | Same embargo event types as `rcv-embargo`, reached by other paths: a second revision cycle, a late vendor that signs the revised embargo, and a teardown that CS.P causes instead of a deliberate termination |

**Why the set is sufficient.** Together the members cover every event-type
column, and every non-member names a member that already covers its event types
and protocol paths. Non-members add regression depth, not breadth, so they run
only on push to `main` (DEMOCI-06-003) and cost a PR nothing. The other
dimensions are covered either by a member (`fcvcv` for multi-vendor), by an
invariant that needs no extra scenario (Invariant 7), or by `demo_check`
assertions that run wherever the scenario runs.

When a scenario is added, decide its membership by this test: does it produce an
event type or protocol path no member produces?
`test_democi_06_002_names_exactly_the_pr_set_event_types` holds DEMOCI-06-002's
event-type list equal to the members' harness constants.

## Workflow Implementation (DEMOCI-06-003)

`.github/workflows/demo-integration.yml` picks the matrix per event (ADR-0052):

- `push` to `main` and `workflow_dispatch` run the whole suite (DEMOCI-05-001).
- On `pull_request`, the `scenarios` job drops every `full_suite_only` entry.
  `full_suite_only` is the inverse of `in_pr_set` and reaches the workflow
  through the generated `.github/demo-scenarios.json` (DEMOCI-11-004).
- The filter is in the `scenarios` job, not a job-level `if:` on a matrix field,
  because job `if:` is evaluated before matrix expansion (DEMOCI-06-004,
  `notes/ci-workflow-authoring.md`).

## RM State-Transition Path Coverage

The event-type matrix cannot tell RM paths apart: `validate_report` is emitted on
both `R → V` and `I → V`, and `add_participant_status_to_participant` on both
`A → D` and `D → A`. A non-linear RM path is therefore verified by a `demo_check`
on the participant's RM state in the scenario script, not by the harness.

| RM transition path | Type | Exercised by |
|---|---|---|
| S → R (report received) | linear | all scenarios |
| R → V (report valid) | linear | all scenarios |
| V → A (report accepted / engaged) | linear | all scenarios |
| A → C (case closed) | linear | all scenarios |
| R → C (stub Invite rejected) | non-linear | `fcv-reject` (CM-11-007) |
| R → I, I → V (invalidated, then re-validated) | non-linear | none — `fvcv-handoff` Variation A, #2050 |
| A → D, D → A (deferred, then resumed) | non-linear | none — `fcvcv` Variation B, #2050 |
| I → C (closed from invalid) | non-linear | none |
| V → D (deferred without accepting) | non-linear | none |

The RM state machine already permits every path above, so exercising one needs
only trigger calls and `demo_check` assertions in a scenario, not new BT nodes.
