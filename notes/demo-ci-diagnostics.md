---
title: Demo Integration CI — Diagnostic Runbook
status: active
description: >
  Targeted diagnostic guide for agents troubleshooting Demo Integration CI
  failures. Covers the 3-layer diagnostic model, per-invariant diagnostic map,
  local Docker run workflow, and CI artifact interpretation.
related_specs:
  - specs/demo-ci.yaml
  - specs/case-ledger-processing.yaml
related_notes:
  - notes/demo-ci.md
  - notes/case-ledger-authority.md
  - notes/sync-ledger-replication.md
  - notes/ci-workflow-authoring.md
  - notes/demo-scenario-authoring.md
relevant_packages:
  - vultron/adapters/driven
  - vultron/adapters/driving/fastapi/routers
  - vultron/core/behaviors/sync
---

# Demo Integration CI — Diagnostic Runbook

**Load this file when**: a Demo Integration CI run has failed and you need
to determine which layer is responsible before filing a bug or pushing a
retry commit. Do **not** push a retry commit without first identifying the
root cause with this guide.

---

## Overview

The Demo Integration CI workflow runs each demo scenario (FV, FVV, FVCV-Extension,
FVCV-Handoff, FCCV-Handoff, FCV) as an independent matrix job inside Docker,
collects JSONL case-ledger replica files, and then runs the scenario-specific
invariant test file against those files. Failures come from one of three layers,
each with its own diagnostic surface.

---

## 3-Layer Diagnostic Model

| Layer | Description | Container log to check | What to search for |
|---|---|---|---|
| **1 — Sent** | Outbound delivery succeeded | Sender container (`finder`, `vendor`, etc.) | `Delivered activity` (INFO) |
| **2 — Received** | Inbox accepted the activity | Receiver container (`case-actor`, `vendor`, etc.) | `Parsing activity from request body` (INFO) |
| **3 — Committed** | Ledger entry written to DataLayer | `case-actor` container | `committed log entry` (INFO) |

### Layer 1 — Sent

**Logger**: `vultron.adapters.driven.demo_http_delivery`
or `vultron.adapters.driven.asgi_emitter`

**Log pattern** (INFO):

```text
Delivered activity <activity_id> to <url> (HTTP 202)
```

**If this line is absent** for an expected activity, the sender never
enqueued the activity (BT failure upstream of the outbox) or HTTP delivery
failed. Check for ERROR lines in the same container around the same time.

### Layer 2 — Received

**Logger**: `uvicorn.error`

**Log pattern** (INFO):

```text
Parsing activity from request body (type=<type>):
<activity JSON>
```

**If this line is absent** but Layer 1 shows a delivery, the receiver's
inbox endpoint returned a non-202 status or a network routing error occurred.
Compare the delivery target URL with the receiver's actual address.

### Layer 3 — Committed

**Logger**: `vultron.core.behaviors.sync.nodes.chain.PersistLogEntryNode`

**Log pattern** (INFO):

```text
PersistLogEntryNode: committed log entry case_id=<id> event_type=<type> log_index=<N> actor_id=<id>
```

**If this line is absent** but Layer 2 shows receipt, the dispatcher routed
the activity but the commit BT failed (missing blackboard key, DataLayer
error, or hash-chain validation failure). Check for ERROR or WARNING lines
from the `vultron.core.behaviors.sync` logger in the `case-actor` container.

---

## Per-Invariant Diagnostic Map

Invariant tests live under `test/ci/invariants/`, one file per scenario. Run
a specific scenario's tests with:

```bash
uv run pytest test/ci/invariants/test_fv_invariants.py -v --tb=short
# or fvv, fvcv_extension, fvcv_handoff, fccv_handoff, fcv
```

### Invariant Status and Diagnostic Focus

| # | Test function | Status | Start at Layer | Resolving issue |
|---|---|---|---|---|
| 1 | `test_invariant_1_local_hash_chain_consistent` | ⏳ xfail (all actors) | 3 — Committed | #789 |
| 2 | `test_invariant_2_cross_actor_hash_agreement` | ⏳ xfail | 3 — Committed | #789 |
| 3 | `test_invariant_3_cross_actor_payload_actor_agreement` | ⏳ xfail | 3 — Committed | #789 |
| 4 | `test_invariant_4_non_empty_payload_snapshot` | ⏳ xfail | 3 — Committed | #789 |
| 5 | `test_invariant_5_expected_event_types_present` | ⏳ xfail | 3 — Committed | #789 |
| 6 | `test_invariant_6_no_rm_state_oscillation` | ✅ passing | 3 — Committed | — |
| 7 | `test_invariant_7_log_terminates_all_rm_closed` | ⏳ xfail | 3 — Committed | #789 |
| 8 | `test_invariant_8_late_joiner_has_full_history` | ⏳ xfail | 2 — Received | #791 |
| 9 | `test_invariant_9_participant_status_schema_completeness` | ⏳ xfail | 3 — Committed | #789 |
| 10 | `test_invariant_10_nested_objects_inlined_in_payload` | ✅ passing | 3 — Committed | — |
| 11 | `test_invariant_11_payload_context_uses_case_uri` | ✅ passing | 3 — Committed | — |
| 12 | `test_invariant_12_genesis_entry_present` | ✅ case-actor, ✅ vendor, ⏳ finder | 2 — Received | #937 (finder) |
| 13 | `test_invariant_13_log_starts_at_genesis` | ✅ case-actor, ✅ vendor, ⏳ finder | 2 — Received | #937 (finder) |
| 14 | `test_invariant_14_no_gaps_in_log_indices` | ✅ all actors | 3 — Committed | — |

**xfail semantics**: An unexpected `XPASS` (xfail test that passed) is
green in CI but visible in the output. When an `XPASS` appears, remove the
`xfail` decorator from the test to promote it to a permanent regression
guard. See `test/ci/README-case-log-ratchet.md` for the full ratchet
workflow.

**Unexpected FAIL on a passing invariant (✅)**: This is a regression.
Check Layers 1→2→3 in order; do not push a retry commit until you have
identified which layer broke.

### Invariant Groups

- **Invariants 1–5, 7, 9**: All xfail pending #789 (CaseActor
  commit-path uniqueness). These test the `case-actor` replica first.
- **Invariant 6**: No RM-state oscillation after `CLOSED`. Tests the
  `add_participant_status` entries in the case-actor log. If this
  regresses, check `ValidateRMTransitionNode` for CLOSED terminal-state
  guard ordering (see `notes/codebase-structure.md`
  § "RM-TERMINAL-GUARD-928").
- **Invariants 12–13**: Log completeness from genesis (`logIndex=0`).
  `finder` is xfail until #937 (join-time history backfill) lands.
- **Invariant 14**: No gaps within an actor's present `logIndex` range.
  Passes for all actors today (including finder's partial fragment).
- **Invariant 8**: Late-joiner history backfill. xfail until #791/#937.

---

## Case-Ledger Endpoint Is Now Per-Replica

**Superseded by ADR-0073.** This section warned that `demo_get_case_ledger`
ignored its `actor_id` path parameter and returned a combined view from the shared
DataLayer. There is no shared DataLayer (DL-07-002), and the route now resolves
`actor_id` through `get_trigger_dl`, which opens *that* actor's store. The
`# noqa: ARG001` on the handler's `actor_id` argument is therefore about the
handler body only — the dependency consumes the parameter.

Implications for diagnostics:

- Treat this endpoint as a **per-replica** view: `GET
  /actors/{actor}/demo/cases/{case}/log` is what that actor holds, and two actors
  legitimately disagree about a case mid-protocol.
- A 404 from it means *that actor* has no such case, which is a real finding, not
  a routing artifact. In particular, a 404 on
  `.../actors/case-actor/demo/cases/.../log` means the CaseActor's own store is
  empty — see issue #2548 for the store-split failure mode that produces it.
- Replica JSONL artifacts under `devlogs/fv/<actor>/<case>-case-ledger.jsonl`
  remain useful for comparing replicas side by side, and for reading history after
  a container has exited.

---

## Local Docker Run Workflow

Use this to reproduce a CI failure locally before investigating logs.

### Step 1 — Build and run

```bash
cd docker
docker compose -f docker-compose-multi-actor.yml build
cd ..
mkdir -p devlogs
DEMO=fv \
VULTRON_SERVER__LOG_LEVEL=DEBUG \
  docker compose -f docker/docker-compose-multi-actor.yml \
  up --abort-on-container-exit --exit-code-from demo-runner
```

A non-zero exit code means the demo runner itself failed (Layer 1 or 2).

### Step 2 — Run the invariant harness

Replace `<scenario>` with the scenario you're diagnosing (`fv`, `fvv`,
`fvcv_extension`, `fvcv_handoff`, `fccv_handoff`, or `fcv`):

```bash
uv run pytest test/ci/invariants/test_<scenario>_invariants.py -v --tb=short
```

Tests skip automatically when `devlogs/` is absent. With artifacts
present, this matches the command CI runs for that matrix entry.

### Step 3 — Collect per-service logs

```bash
mkdir -p /tmp/demo-logs
docker compose -f docker/docker-compose-multi-actor.yml logs \
  > /tmp/demo-logs/combined.log 2>&1

for svc in finder vendor coordinator case-actor actor5 demo-runner; do
  docker compose -f docker/docker-compose-multi-actor.yml logs "$svc" \
    > "/tmp/demo-logs/${svc}.log" 2>&1 || true
done
```

### Step 4 — Tear down

```bash
docker compose -f docker/docker-compose-multi-actor.yml down -v
```

---

## Interpreting CI Artifacts

CI uploads two artifact bundles per matrix entry. Both are available from the
Actions run summary page under **Artifacts**, named after the scenario.

### `<demo>-case-logs` (always uploaded)

Where `<demo>` is the scenario name: `fv`, `fvv`, `fvcv-extension`,
`fvcv-handoff`, `fccv-handoff`, or `fcv`.

Path in artifact: `devlogs/`

JSONL file layout (example for `fv`):

```text
devlogs/fv/finder/<case-id-slug>-case-ledger.jsonl
devlogs/fv/vendor/<case-id-slug>-case-ledger.jsonl
devlogs/fv/case-actor/<case-id-slug>-case-ledger.jsonl
```

These are the replica files the invariant harness reads. Download and place
under the repo root `devlogs/` to re-run the harness locally against the CI
artifacts:

```bash
uv run pytest test/ci/invariants/test_<scenario>_invariants.py -v --tb=short
```

Each JSONL line is a `CaseLedgerEntry` object. Key fields:

| Field | Description |
|---|---|
| `logIndex` | Sequential position in the canonical log |
| `entryHash` | SHA-256 of this entry's content |
| `prevLogHash` | `entryHash` of the previous entry (genesis = 64 zeros) |
| `eventType` | Protocol event name (e.g., `accept_report`) |
| `payloadSnapshot` | Verbatim AS2 activity that caused the entry |
| `disposition` | `recorded` (accepted) or `rejected` |
| `case_id` | Case URI this entry belongs to |

### `<demo>-container-logs` (uploaded on failure only)

Path in artifact: `/tmp/demo-logs/`

Files: `combined.log`, `finder.log`, `vendor.log`, `coordinator.log`,
`case-actor.log`, `actor5.log`, `demo-runner.log`.

**Correlating JSONL artifacts with container logs**: Use the `case_id`
from a failing JSONL entry as a grep anchor in the container logs, then
widen the time window by a few seconds to see surrounding context.

**Log level**: CI always runs with `VULTRON_SERVER__LOG_LEVEL=DEBUG` so
container logs include full tracebacks and state-machine transitions in
addition to INFO-level delivery/receipt/commit lines.

---

## Diagnostic Checklist (Quick Reference)

1. **Identify the failing invariant** from the pytest output.
2. **Look up the starting layer** in the per-invariant table above.
3. **Check the relevant container log** for the corresponding log pattern.
4. **Work up the layers** (1→2→3) until you find the first missing
   pattern — that is the broken layer.
5. **File a bug** with: failing invariant, container log excerpt, layer
   determination, and JSONL entry (if relevant).
6. **Do not push a retry commit** without a root-cause determination.

---

## Async Race Window Patterns

Demo CI timeouts and out-of-order state failures are usually one of two
shapes. Recognizing the shape tells you which layer broke and whether the
fix is in the demo script or the protocol code.

### The BackgroundTasks delivery gap

Every trigger endpoint (`validate-report`, `engage-case`, etc.) returns
HTTP 202 before its protocol effects are committed. The effect — a
`ParticipantStatus` write, a `CaseLedgerEntry`, a replica arriving on
another container — lands later, in a `BackgroundTasks` callback. A demo
step that depends on that effect must wait for it explicitly. If it does
not, one of two failure modes appears in CI:

**Shape A — wrong precondition state**: the dependent step runs before the
effect commits. The BT or use case detects the missing state (e.g.,
`TransitionParticipantRMtoAccepted` rejects a 422 because RM.VALID has not
committed yet) and the demo fails with a protocol-level error that looks
like a bug rather than a timing issue.

**Shape B — inconsistent replica comparison**: the demo reads a replica
before it has all entries, computes a result (e.g., ledger tail index,
state diff), and either the assertion passes on wrong data or the timeout
fires while the replica is mid-delivery. Both produce flaky results across
CI runs with different container load.

### Recognizing causal vs temporal waits

Ask one question about each `wait_for_*` call: **if this wait times out
and the next step runs anyway, does the next step operate on state that was
never established?**

- **Yes** → the wait is a causal precondition. The next step depends on it.
  Wrap it in `demo_gate`. A `demo_check` wrapper records the miss and
  continues — the dependent step then runs blind, producing a confusing
  secondary failure that obscures the root cause.

- **No** → the wait is temporal (service liveness, transport backoff, or a
  post-hoc verification). `demo_check` is appropriate. Identify it as
  temporal at the call site per EDF-06-006 so it is not mistaken for a
  causal gate in a future edit.

Common causal waits (should be `demo_gate`):

| Wait | Precondition for |
|---|---|
| `wait_for_participant_rm_state` to RM.VALID | `engage-case` trigger (rejects at 422 if RM.VALID not committed) |
| `wait_for_case_on_container` (replica present) | `wait_for_contiguous_ledger_coverage` (needs genesis hash to anchor chain) |
| `wait_for_contiguous_ledger_coverage` | any state comparison across replicas |
| `wait_for_event_type_in_ledger` (close phase) | reading ledger tail on a complete replica |

Common temporal waits (may stay `demo_check` if they do not gate a
downstream step):

| Wait | Why temporal |
|---|---|
| `wait_for_case_participants` | cross-container delivery budget; timeout is a time-based estimate, not a protocol precondition the system can accelerate |

### Diagnosing a timeout in CI

1. Find the `demo_check`/`demo_gate` failure message in `demo-runner.log`.
2. Check which `wait_for_*` timed out and note what follows it in the
   scenario script.
3. Apply the causal-vs-temporal test above to the timed-out wait.
4. If causal: the wait should be a `demo_gate`. Look for a `demo_check`
   wrapper or bare `wait_for_*` call (no wrapper) — bare calls raise
   `AssertionError` directly, bypassing the failure accumulator entirely.
5. If temporal: the timeout budget may be under-sized for the CI
   environment. Check the comment at the `wait_for_*` call site in
   `vultron/demo/helpers/polling.py` for the EDF-06-006 justification.
   Raising the budget is a last resort; verify first that the underlying
   delivery is not silently failing.

### Bare calls are not equivalent to `demo_gate`

A `wait_for_*` call with no wrapper looks like a gate but is not:

- It raises `AssertionError` directly on timeout, bypassing the demo
  harness's failure accumulator.
- The scenario may have accumulated earlier `demo_check` failures that are
  lost when the bare raise propagates to `scenario_harness`.
- Downstream steps do not get the structured "precondition not met" skip
  that `demo_gate` provides; they simply never run because the exception
  terminates the scenario.

Wrap all `wait_for_*` calls in either `demo_gate` (causal) or `demo_check`
(temporal, non-gating). No bare calls.

### Anti-pattern examples

```python
# ❌ Wrong — demo_check lets the next step run on uncommitted RM.VALID state
with demo_check(f"{actor.id_} reached RM.VALID before engage-case"):
    wait_for_participant_rm_state(
        client=vendor_client, case_id=case.id_,
        actor_id=actor.id_, expected_states={RM.VALID, RM.ACCEPTED},
    )
vendor_engages_case(...)  # may 422 if RM.VALID not yet committed

# ❌ Wrong — bare call raises AssertionError directly, bypasses accumulator
wait_for_contiguous_ledger_coverage(
    client=finder_client, case_id=case.id_,
    expected_tail_index=vendor_tail_index,
)
compare_replica_state(...)  # runs on partial replica if wait timed out

# ✅ Correct — demo_gate blocks dependent steps when precondition is unmet
with demo_gate(f"{actor.id_} reached RM.VALID before engage-case"):
    wait_for_participant_rm_state(
        client=vendor_client, case_id=case.id_,
        actor_id=actor.id_, expected_states={RM.VALID, RM.ACCEPTED},
    )
vendor_engages_case(...)  # skipped (not run) if gate failed
```

A `demo_check` failure produces a confusing *secondary* failure downstream — a
422 from a trigger, a wrong snapshot comparison, a ledger assertion on a partial
replica — that obscures the root cause. The enforcement rule lives in
`vultron/demo/AGENTS.md` § "Never Wrap a Causal Wait in `demo_check`"; the
normative requirements are EDF-06-005 and EDF-06-006.

### Demo Devlog Race: Wait for Replica Before Dumping

(DEMO-DEVLOG-RACE, 2026-06-18)

Demo phases that write JSONL devlogs will miss recently committed canonical
ledger entries if they run before the async `Announce(CaseLedgerEntry)` fan-out
has been processed and stored by the replica actor.

**Pattern**: after any phase that commits a new canonical ledger entry, query the
sender's current tail hash and poll until the replica acknowledges it before
writing the devlog:

```python
vendor_entries = _get_log_entries_for_case(vendor_client, case.id_)
if vendor_entries:
    tail = max(vendor_entries, key=lambda e: e["log_index"])
    wait_for_finder_log_entry(finder_client, case.id_, tail["entry_hash"])
```

Apply this poll-until-hash pattern after every phase that introduces a new ledger
tail before a devlog dump. This is the same pattern used in
`_phase_sync_verification`, and it ensures dump artifacts are always consistent
with the replica's committed state.

---

## Ratchet Workflow Reference

When a fix lands that resolves an xfail invariant, see
`test/ci/README-case-log-ratchet.md` for the step-by-step process to
promote the test from `XFAIL` to a permanent regression guard.

## Trace Shared Helper Layers Before Declaring an Event Unemitted

In the demo suite, protocol activity is emitted from shared helpers in
`vultron/demo/helpers/workflow.py` (e.g. `receiver_engages_case()`,
`run_direct_path_rm_triage()`), not from the scenario files. Grepping a scenario
file — or even all of `vultron/demo/scenario/` — finds nothing and invites the
false conclusion that no code emits the event. Search the helper and
semantic-registry layers, and confirm against `graphify explain "<function>"`
call edges, before asserting absence. CONCERN-2243 filed a Concern on this basis
for an event emitted by all nine scenarios.

Source: CONCERN-2243
