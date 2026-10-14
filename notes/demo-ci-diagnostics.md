---
title: Demo Integration CI — Diagnostic Runbook
status: active
kind: guidance
description: >
  Runbook for a failed Demo Integration CI run: the three log layers, the
  per-invariant diagnostic map (ratcheted against the invariant factory), the
  local Docker reproduction, CI artifacts, and the causal-versus-temporal wait
  test for demo timeouts.
related_specs:
  - specs/demo-ci.yaml
  - specs/case-ledger-processing.yaml
  - specs/multi-actor-demo.yaml
  - specs/case-management.yaml
  - specs/event-driven-control-flow.yaml
related_notes:
  - notes/demo-ci-invariants.md
  - notes/demo-ci-scenario-coverage.md
  - notes/case-ledger-authority.md
  - notes/sync-ledger-replication.md
  - notes/ci-workflow-authoring.md
  - notes/demo-scenario-authoring.md
  - notes/demo-scenario-registry.md
  - notes/participant-role-management.md
  - notes/event-driven-control-flow.md
relevant_packages:
  - vultron/adapters/driven
  - vultron/adapters/driving/fastapi/routers
  - vultron/core/behaviors/sync
  - test/ci/invariants
---

# Demo Integration CI — Diagnostic Runbook

**Load this file when** a Demo Integration CI run has failed. Find the broken
layer before you file a bug or push a retry commit; a retry without a root cause
hides the defect.

Each scenario runs as its own matrix job in Docker, dumps the JSONL case-ledger
replicas, and a separate job runs that scenario's invariant harness against them.
The matrix comes from the generated `.github/demo-scenarios.json` (ADR-0098); a
pull request runs the DEMOCI-06-002 minimum set and a push to `main` runs all of
them.

---

## 3-Layer Diagnostic Model

| Layer | Meaning | Container log | Log line |
|---|---|---|---|
| **1 — Sent** | Outbound delivery succeeded | Sender (`finder`, `vendor`, …) | `Delivered activity <id> to <url> (HTTP 202)` (INFO, `vultron.adapters.driven.http_delivery`) |
| **2 — Received** | Inbox accepted the activity | Receiver (`case-actor`, `vendor`, …) | `Parsing activity from request body (type=…)` (DEBUG, `uvicorn.error`) |
| **3 — Committed** | Ledger entry written | `case-actor` | `PersistLogEntryNode: committed log entry case_id=… event_type=… log_index=… actor_id=…` (INFO) |

Walk the layers 1→2→3 and stop at the first missing line:

- **No Layer 1 line**: the sender never enqueued the activity (a BT failure
  upstream of the outbox) or HTTP delivery failed. Look for ERROR lines in the
  sender around the same time.
- **Layer 1 but no Layer 2**: the receiver's inbox returned non-202, or the
  delivery URL is wrong. Compare the target URL with the receiver's address.
- **Layer 2 but no Layer 3**: dispatch happened but the commit tree failed
  (missing blackboard key, DataLayer error, hash-chain validation). Look for
  ERROR or WARNING from `vultron.core.behaviors.sync` in `case-actor`.

---

## Per-Invariant Diagnostic Map

Harnesses live under `test/ci/invariants/`, one per scenario, at
`test_<name_>_invariants.py` (hyphens become underscores). The generated table in
`test/ci/README-case-log-ratchet.md` lists them (DEMOCI-11-003). Run one with:

```bash
uv run pytest test/ci/invariants/test_fv_invariants.py -v --tb=short
```

### Invariant Status and Diagnostic Focus

This is the universal set that `make_universal_invariant_tests()` in
`test/ci/invariants/universal_harness.py` injects into every harness.
`test/ci/invariants/test_diagnostic_map_sync.py` ratchets the table against that
function, so adding or retiring an invariant fails until the row follows.

**Status** is the ratchet state, not today's pass/fail: **active** (no `xfail`;
a failure is a regression) or **⏳ xfail — #N** (a known defect owns it). There
is no per-actor state. `test_no_param_level_marks_on_factory_arguments` rejects
a `marks=pytest.mark.xfail(...)` on `_CHAIN_ACTORS` or
`_XXX_EXPECTED_EVENT_TYPES`, because it would silence some cases of a row the
table calls active. Put an xfail on the invariant in `universal_harness.py`.

**Start at Layer** names the layer that most often explains the invariant: a
missing entry or event → Layer 1; a replica that is incomplete or disagrees with
a peer → Layer 2; an entry that is present but malformed → Layer 3.

| # | Test function | Status | Start at Layer |
|---|---|---|---|
| 1 | `test_invariant_1_local_hash_chain_consistent` | active | 3 — Committed |
| 2 | `test_invariant_2_cross_actor_hash_agreement` | active | 2 — Received |
| 3 | `test_invariant_3_cross_actor_payload_actor_agreement` | active | 2 — Received |
| 4 | `test_invariant_4_non_empty_payload_snapshot` | active | 3 — Committed |
| 5 | `test_invariant_5_expected_event_types_present` | active | 1 — Sent |
| 6 | `test_invariant_6_no_rm_state_oscillation` | active | 3 — Committed |
| 7 | `test_invariant_7_log_terminates_all_rm_closed` | active | 1 — Sent |
| 9 | `test_invariant_9_participant_status_schema_completeness` | active | 3 — Committed |
| 10 | `test_invariant_10_nested_objects_inlined_in_payload` | active | 3 — Committed |
| 11 | `test_invariant_11_payload_context_uses_case_uri` | active | 3 — Committed |
| 12 | `test_invariant_12_genesis_entry_present` | active | 2 — Received |
| 13 | `test_invariant_13_log_starts_at_genesis` | active | 2 — Received |
| 14 | `test_invariant_14_no_gaps_in_log_indices` | active | 2 — Received |
| 15 | `test_invariant_15_cs_state_transitions_observed` | active | 1 — Sent |
| 16 | `test_invariant_16_causal_edges_in_ledger_order` | active | 3 — Committed |
| 18 | `test_invariant_18_no_participant_act_after_case_fully_closed` | active | 3 — Committed |
| — | `test_invariant_clp13_no_rejected_invite_entries` | active | 3 — Committed |
| — | `test_invariant_clp07_unique_payload_snapshot_ids` | active | 3 — Committed |
| — | `test_invariant_clp14_timestamp_invariants` | active | 3 — Committed |
| — | `test_invariant_per_actor_replica_no_rm_state_oscillation` | active | 2 — Received |
| — | `test_invariant_per_actor_replica_rm_closed_termination` | active | 2 — Received |
| — | `test_invariant_per_actor_replica_participant_status_schema_completeness` | active | 2 — Received |
| — | `test_invariant_per_actor_replica_cs_state_transitions_observed` | active | 2 — Received |

**Match a failure to a row by test function name**, never by `#`. The number is
a label: it skips 8 (scenario-local, below) and the unnumbered rows are named for
the spec clause they check.

**Keep any new xfail as narrow as its defect.** A marker on a check that
aggregates several properties silences all of them, and with `strict=False` an
`XPASS` is green, so the silence does not lift when the defect is fixed. That is
why the four `per_actor_replica_*` checks are separate tests (ISSUE-3385). When
an `XPASS` appears, remove the marker; `test/ci/README-case-log-ratchet.md` has
the promotion steps.

### Reading individual invariants

- **Invariant 8 (late-joiner backfill) is scenario-local**, so it is not a row.
  It names a specific early and late actor, so each harness except `fcv_reject`
  declares one test per late joiner, named
  `test_<scenario>_<late_actor>_late_joiner_has_full_history` (FV's keeps the
  `test_invariant_8_` prefix). Start at Layer 2. Grep
  `late_joiner_has_full_history` to enumerate them.
- **Invariant 16 is injected only when the harness passes `narrative_path`**,
  because it reads the narrative's `causal_edges:` (DEMOMA-22-005).
  `test_every_harness_passes_a_narrative_path` enforces the argument.
- **Invariant 17 is injected only when the harness passes `joined_invitees > 0`**.
  It checks that the ledger holds a full-case Invite and a reply to it for each
  invited actor (CM-11-010, CM-11-011). A failure means an invitee joined
  without judging the case: start at Layer 2 for the missing Invite or reply.
- **Invariant 18** runs `case_closure_violations` from
  `vultron/demo/helpers/milestones.py` over the `case-actor` log (CM-23-013). A
  failure names a participant act committed after `case_fully_closed`. Check the
  post-close guard `CaseOpenToExternalWritesNode` and the scenario's
  `close_case_owner_last` order.
- **Invariant 7 and the `per_actor_replica_*` checks** fail when the
  CASE_MANAGER's own RM.CLOSED entry is missing. Check that
  `CommitRMClosureEntriesNode` ran for the CASE_MANAGER on the owner-Leave path
  and that the semantic got a `WireRenderPort` (every semantic gets one through
  `with_received_baseline_ports()`; without it the commit raises
  `VultronWiringError`) (#3930).
- **`per_actor_replica_*` are the replica halves of 6, 7, 9 and 15.** The
  numbered ones run on the `case-actor` log; these run each other replica in
  isolation. A red `per_actor_replica_*` with its numbered twin green means the
  property holds on the authority and broke in replication: start at Layer 2.
  They do not compare replicas with each other; the `Actor '<id>':` prefix names
  the failing one. The three status-dependent ones skip a replica with no
  `add_participant_status_to_participant` entries.
- **`per_actor_replica_rm_closed_termination` checks a leaver's own closure
  only.** A closed participant is sent nothing after the entries recording its
  own closure (CM-23-004), so the check asserts each leaver's replica ends
  exactly at its last own-closure entry on the `case-actor` log
  (`own_closure_tail_index`), with the leaver at `CLOSED`. Ending later means it
  was sent content after leaving; ending earlier means it missed its own closure
  step. The late-joiner checks likewise compare only up to the late actor's own
  last entry.
- **Invariant 6** (no RM oscillation after `CLOSED`): check guard ordering in
  `ValidateRMTransitionNode` — see `notes/participant-role-management.md`
  § "RM Terminal Guard Must Run Before the Same-State Shortcut".
- **Invariants 1 and 12–14** are parametrized per `_CHAIN_ACTORS` entry, so the
  failing case id names the short replica. Read it before assuming the whole
  fan-out broke.
- **Invariants 2 and 3** compare only indices two or more replicas share. A
  replica can lag mid-protocol, so confirm the demo reached its final phase
  first. A missing index is 12–14 territory.
- **Invariant 5** (expected `eventType` present): do not fix a failure by editing
  the harness constant. The universal block is `_UNIVERSAL_EVENT_TYPES`,
  ratcheted by `test/ci/invariants/test_universal_event_types.py`.

---

## Trace Shared Helper Layers Before Declaring an Event Unemitted

Demo protocol activity is emitted from shared helpers in
`vultron/demo/helpers/workflow.py` (`receiver_engages_case()`,
`run_direct_path_rm_triage()`, …), not from scenario files. Grepping
`vultron/demo/scenario/` finds nothing and suggests no code emits the event.
Search the helper and semantic-registry layers before asserting absence
(CONCERN-2243).

---

## The Case-Ledger Endpoint Is Per-Replica

`GET /actors/{actor}/demo/cases/{case}/log` returns what *that actor's* store
holds (ADR-0073), so two actors legitimately disagree mid-protocol. A 404 means
that actor has no such case, which is a real finding. A 404 for `case-actor`
means the CaseActor's own store is empty (#2548).

---

## Local Docker Run Workflow

Reproduce a CI failure locally before reading logs:

```bash
docker compose -f docker/docker-compose-multi-actor.yml build
mkdir -p devlogs
DEMO=fv VULTRON_SERVER__LOG_LEVEL=DEBUG \
  docker compose -f docker/docker-compose-multi-actor.yml \
  up --abort-on-container-exit --exit-code-from demo-runner
uv run pytest test/ci/invariants/test_fv_invariants.py -v --tb=short
docker compose -f docker/docker-compose-multi-actor.yml logs > /tmp/demo-logs.log 2>&1
docker compose -f docker/docker-compose-multi-actor.yml down -v
```

A non-zero exit from `up` means the demo runner itself failed. `DEMO` takes the
hyphenated scenario name; the harness file uses underscores. The harness skips
when `devlogs/` is absent.

---

## Interpreting CI Artifacts

Each matrix entry uploads, under the run's **Artifacts**:

- **`<demo>-case-logs`** (always):
  `devlogs/<demo>/<actor>/<case-slug>-case-ledger.jsonl` plus
  `dump-manifest.json`. Unpack it under the repo root's `devlogs/` and run the
  harness locally against it. Each line is a serialized `CaseLedgerEntry`
  (`vultron/core/models/case_ledger_entry.py`), camelCase on the wire.
- **`<demo>-container-logs`** (on failure only): `combined.log` and one log per
  service. Use a failing entry's `caseId` as the grep anchor.

CI runs the containers at `VULTRON_SERVER__LOG_LEVEL=DEBUG`, so the logs include
the Layer 2 line, tracebacks and state transitions.

---

## Async Race Window Patterns

Every trigger endpoint returns 202 before its effects commit; the
`ParticipantStatus` write, ledger entry, or replica lands later in a
`BackgroundTasks` callback. A demo step that depends on that effect must wait
for it. When it does not, CI shows one of two shapes:

- **Wrong precondition state**: the next step runs before the effect commits
  and fails with a protocol error (e.g. `engage-case` 422 because RM.VALID has
  not committed) that looks like a bug rather than timing.
- **Inconsistent replica comparison**: the demo reads a replica before it holds
  every entry, so an assertion passes on wrong data or times out mid-delivery.

### Causal vs temporal waits

Ask of each `wait_for_*`: **if it times out and the next step runs anyway, does
that step operate on state that was never established?**

- **Yes** → causal: wrap it in `demo_gate`, which skips dependent steps.
  `demo_check` would record the miss and let the next step run blind, producing a
  confusing secondary failure.
- **No** → temporal (liveness, transport backoff, post-hoc verification):
  `demo_check`, labelled temporal at the call site (EDF-06-006).

Never leave a `wait_for_*` bare. A bare call raises `AssertionError` straight
past the failure accumulator, losing earlier `demo_check` failures. The rule is
`vultron/demo/AGENTS.md` § "Never Wrap a Causal Wait in `demo_check`"
(EDF-06-005, EDF-06-006).

Typical causal waits: `wait_for_participant_rm_state` before `engage-case`;
`wait_for_case_on_container` before `wait_for_replica_ledger_coverage`;
`wait_for_replica_ledger_coverage` before any cross-replica comparison
(`run_sync_verification_phase` composes both); every participant at
`RM.CLOSED` in the CASE_MANAGER's store before the Case Owner's `Leave`
(`close_case_owner_last`, CM-23-015). `wait_for_case_participants` is typically
temporal.

```python
# Wrong: demo_check lets engage-case run on an uncommitted RM.VALID
with demo_check(f"{actor.id_} reached RM.VALID"):
    wait_for_participant_rm_state(...)
vendor_engages_case(...)  # may 422

# Right: demo_gate skips engage-case if the precondition is unmet
with demo_gate(f"{actor.id_} reached RM.VALID"):
    wait_for_participant_rm_state(...)
vendor_engages_case(...)
```

### Diagnosing a timeout

1. Find the `demo_check`/`demo_gate` failure in `demo-runner.log` and the step
   that follows the timed-out wait.
2. Apply the causal-vs-temporal test. A causal wait under `demo_check` or bare is
   the defect.
3. If temporal, the budget may be small for CI, but first confirm the delivery
   is not silently failing; raising a budget is the last resort.

### Demo Devlog Race: Wait for Replica Before Dumping

A devlog dump misses entries still in `Announce(CaseLedgerEntry)` fan-out. After
any phase that commits a new canonical entry, wait for the replicas before the
dump:

```python
wait_for_replica_ledger_coverage(
    auth_client=vendor_client,
    replicas=[(finder_client, "Finder")],
    case_id=case.id_,
    phase_label="notes phase",
)
```

The helper waits for *contiguous* coverage up to the authority's tail, since a
tail-hash-only wait misses an entry that arrives after the tail. Case closure is
the exception: no replica covers the authority's tail after it (CM-23-004), so
`close_case_owner_last` instead waits for each leaver's replica to end at its own
closure (`wait_for_replica_ledger_ending_at`). A scenario module never calls
`_get_log_entries_for_case` or `wait_for_contiguous_ledger_coverage` itself
(DEMOMA-23-006).
