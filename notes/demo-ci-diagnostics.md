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
  - specs/multi-actor-demo.yaml
related_notes:
  - notes/demo-ci-invariants.md
  - notes/demo-ci-scenario-coverage.md
  - notes/case-ledger-authority.md
  - notes/sync-ledger-replication.md
  - notes/ci-workflow-authoring.md
  - notes/demo-scenario-authoring.md
  - notes/demo-scenario-registry.md
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

The Demo Integration CI workflow runs each demo scenario as an independent
matrix job inside Docker, collects JSONL case-ledger replica files, and then
runs that scenario's invariant test file against them. The scenario set and its
harness files come from `.github/demo-scenarios.json`, which CI resolves the
matrix from; a pull request runs the DEMOCI-06-002 minimum validation subset and
push-to-main runs all of them. ADR-0098 moves the declaration of which scenarios
exist into the demo modules themselves and makes that JSON a generated
projection — until it lands, the JSON is still hand-maintained. Failures come
from one of three layers, each with its own diagnostic surface.

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

Invariant tests live under `test/ci/invariants/`, one file per scenario.
`.github/demo-scenarios.json` is the sole scenario→harness registry. Run one
scenario's tests with the harness file that registry names, for example:

```bash
uv run pytest test/ci/invariants/test_fv_invariants.py -v --tb=short
# harness files exist for fv, fvv, fvcv_extension, fvcv_handoff,
# fccv_extension, fccv_handoff, fcv, fcv_reject, and fcvcv
```

### Invariant Status and Diagnostic Focus

The table below is the **universal** set — the invariants
`make_universal_invariant_tests()` in
`test/ci/invariants/universal_harness.py` injects into every scenario harness.
`test/ci/invariants/test_diagnostic_map_sync.py` ratchets this table against
that function, so a new or retired invariant fails here until the row is added
or removed.

**Status** is the ratchet state read off the harness, not today's pass/fail:

- **active** — no `xfail` marker. A failure is a real regression; work the
  layers.
- **⏳ xfail** — a known defect owns it, named in the marker's `reason`. The job
  stays green while it fails.

There is no third state, and no per-actor state: each invariant gets exactly one
cell, so `active` means every case of that invariant is a live guard. A
`marks=pytest.mark.xfail(...)` entry on a harness's `_CHAIN_ACTORS` or
`_XXX_EXPECTED_EVENT_TYPES` list would xfail *some* cases of a row this table
calls `active`, where no cell could show it — so
`test_diagnostic_map_sync.py::test_no_param_level_marks_on_factory_arguments`
rejects that form outright. An xfail belongs on the invariant in
`universal_harness.py`, where this table can record it. (The retired table in
`test/ci/README-case-log-ratchet.md` did carry per-actor state, as
"✅ case-actor, ✅ vendor, ⏳ finder" — and that is one of the columns that
rotted.)

**How to read "Start at Layer"**: it names the layer whose failure most often
explains this invariant. Check it first, then walk 1→2→3 to find the first
missing log pattern.

- A missing **entry or event** → start at Layer 1 (was it ever sent?).
- A replica that is **incomplete or disagrees with a peer** → start at Layer 2
  (did the fan-out arrive?).
- An entry that is **present but malformed** → start at Layer 3 (did the commit
  write it wrong?).

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
| — | `test_invariant_clp13_no_rejected_invite_entries` | active | 3 — Committed |
| — | `test_invariant_clp14_timestamp_invariants` | active | 3 — Committed |
| — | `test_invariant_per_actor_replica_no_rm_state_oscillation` | active | 2 — Received |
| — | `test_invariant_per_actor_replica_rm_closed_termination` | active | 2 — Received |
| — | `test_invariant_per_actor_replica_participant_status_schema_completeness` | active | 2 — Received |
| — | `test_invariant_per_actor_replica_cs_state_transitions_observed` | active | 2 — Received |

**The `#` column is a historical label, not an index.** It skips 8 (that
invariant is scenario-local — see below) and runs out entirely for the last
six, which are named for the spec clause or the property they check rather
than taking the next number. Match a pytest failure to a row by **test
function name**, never by number or position.

**The four `per_actor_replica_*` rows are the replica-side halves of 6, 7, 9
and 15.** Those four run against `auth_entries(replicas)`, which resolves to the
`case-actor` log; the `per_actor_replica_*` rows run the same checks against
each *other* replica in isolation, and are the only place those properties are
asserted for non-`case-actor` replicas (ISSUE-2411 Gap 1). So a failure in a
`per_actor_replica_*` row with its numbered twin green means the property holds
on the authority and broke in replication — start at Layer 2. They were one
aggregate test under one `xfail` until ISSUE-3385; splitting them is what lets a
future known defect be scoped to the one property it owns.

**Invariant 8 is scenario-local, not universal — and there is more than one of
it.** Late-joiner backfill has to name a specific early actor and late actor,
which differ per scenario, so the factory cannot inject it. Instead every
harness but `fcv_reject` declares its own, one per late-joining actor in that
scenario — a dozen-plus tests in total, all active, all calling
`check_late_joiner_has_full_history`. Only FV's keeps the historical
`test_invariant_8_` prefix; the rest are named
`test_<scenario>_<late_actor>_late_joiner_has_full_history` (e.g.
`test_fcvcv_c2_late_joiner_has_full_history`). So:

- A failing test whose name ends `_late_joiner_has_full_history` is this
  invariant, whatever the prefix, and is **not** a row in the table above.
- Start at Layer 2 (did the backfill fan-out arrive?), and read the failure for
  which pair it compared — the test names the late actor, not the early one.
- To enumerate them, grep `late_joiner_has_full_history` across
  `test/ci/invariants/`; this note deliberately does not list them, because a
  list here would rot exactly the way the table above did.

**Invariant 16 is conditional.** The factory injects it only when the harness
passes `narrative_path`, because it reads the scenario narrative page's
`causal_edges:` front-matter (DEMOMA-22-005). Omitting the argument is legal
and produces a harness that collects and passes with no causal-edge check at
all, so `test_diagnostic_map_sync.py::test_every_harness_passes_a_narrative_path`
asserts every harness in `.github/demo-scenarios.json` supplies one. It is the
only invariant whose *presence* is conditional; every other row above is
injected unconditionally.

**xfail semantics**: An unexpected `XPASS` (xfail test that passed) is
green in CI but visible in the output. When an `XPASS` appears, remove the
`xfail` decorator from the test to promote it to a permanent regression
guard. See `test/ci/README-case-log-ratchet.md` for the full ratchet
workflow.

**There are currently no `xfail`s in the universal set** — every row above is
active. Before adding one, make it as narrow as the defect: a marker over a
check that aggregates several independent properties silences all of them, and
`strict=False` means the silence does not lift when the defect is fixed, because
an `XPASS` is green too. That is what ISSUE-3385 reported, and why the four
`per_actor_replica_*` checks are separate tests rather than one.

**Unexpected FAIL on an active invariant**: This is a regression.
Check Layers 1→2→3 in order; do not push a retry commit until you have
identified which layer broke.

### Invariant Groups

- **Invariant 7 and the four `per_actor_replica_*` checks**: these five were the
  universal set's only `xfail`s, all naming **#2505** — the CaseActor never
  reached `RM.CLOSED`, because its own closure transition was written to its
  store and never recorded as a ledger entry, so no replica could observe it.
  All five are now active guards. If one goes red, the CASE_MANAGER's terminal
  entry is missing again: check that `CommitCaseActorRMClosedEntryNode` ran on
  the owner-Leave path and that `CLOSE_CASE` still receives a `WireRenderPort`
  (without it the node hard-fails).
- **The `per_actor_replica_*` checks are per-replica, not cross-replica.** They
  do not compare replicas against each other. Each runs every non-`case-actor`
  replica **in isolation** (`{actor: entries}`, so `auth_entries()` falls back
  to that actor's own log). A failure therefore means *one replica*
  independently violates a state invariant; the `Actor '<id>':` prefix on each
  violation names which. Do not go looking for disagreement between actors —
  that is invariants 2 and 3.
- The three status-dependent ones skip any replica holding no
  `add_participant_status_to_participant` entries; the RM-oscillation one does
  not, because `close_case` entries also carry RM state.
- **Invariant 6**: No RM-state oscillation after `CLOSED`. Tests the
  `add_participant_status` entries in the case-actor log. If this
  regresses, check `ValidateRMTransitionNode` for CLOSED terminal-state
  guard ordering (see `notes/codebase-structure.md`
  § "RM-TERMINAL-GUARD-928").
- **Invariants 12–14**: log completeness and contiguity from genesis
  (`logIndex=0`). These, plus invariant 1, are the per-actor parametrized
  checks — one test case per entry in the harness's `_CHAIN_ACTORS` — so the
  failing case id names which replica is short. Read it before assuming the
  whole fan-out broke.
- **Invariants 2 and 3**: the actual cross-replica agreement checks — the same
  `logIndex` must carry the same `entryHash` and the same
  `payloadSnapshot.actor` in every replica that holds it. Mid-protocol
  divergence is normal (a replica legitimately lags), so confirm the demo
  reached its final phase before treating a mismatch as a defect. Note these
  compare only indices that *two or more* replicas share; an index one actor
  is missing entirely is invariant 12–14 territory.
- **Invariant 5**: expected `eventType` presence. The leading entries of every
  harness's `_XXX_EXPECTED_EVENT_TYPES` are the DEMOMA-16-001 universal block,
  ratcheted by `test/ci/invariants/test_universal_event_types.py` — read the
  members from `_UNIVERSAL_EVENT_TYPES` there rather than a count restated here
  (MS-16-001). Do not "fix" a failure by editing the constant.

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

Replace `<scenario>` with the scenario you're diagnosing, spelled as its
harness file is (underscores, not hyphens — `fvcv_extension`, not
`fvcv-extension`):

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

Where `<demo>` is the `demo:` value from `.github/demo-scenarios.json` —
hyphenated (`fvcv-extension`), unlike the underscored harness filenames.

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
