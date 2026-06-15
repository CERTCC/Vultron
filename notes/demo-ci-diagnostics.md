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

The Demo Integration CI job runs a two-actor Vultron scenario end-to-end
inside Docker, collects JSONL case-ledger replica files, and then runs the
`case_ledger_invariants` harness against those files. Failures come from
one of three layers, each with its own diagnostic surface.

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

All tests are in `test/ci/test_case_ledger_invariants.py` and tagged
`@pytest.mark.case_ledger_invariants`. Run them with:

```bash
uv run pytest -m case_ledger_invariants -v --tb=short
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

## Local Docker Run Workflow

Use this to reproduce a CI failure locally before investigating logs.

### Step 1 — Build and run

```bash
cd docker
docker compose -f docker-compose-multi-actor.yml build
cd ..
mkdir -p devlogs
DEMO=two-actor \
VULTRON_SERVER__LOG_LEVEL=DEBUG \
  docker compose -f docker/docker-compose-multi-actor.yml \
  up --abort-on-container-exit --exit-code-from demo-runner
```

A non-zero exit code means the demo runner itself failed (Layer 1 or 2).

### Step 2 — Run the invariant harness

```bash
uv run pytest -m case_ledger_invariants -v --tb=short
```

Tests skip automatically when `devlogs/` is absent. With artifacts
present, this is the same command CI runs.

### Step 3 — Collect per-service logs

```bash
mkdir -p /tmp/demo-logs
docker compose -f docker/docker-compose-multi-actor.yml logs \
  > /tmp/demo-logs/combined.log 2>&1

for svc in finder vendor coordinator case-actor vendor2 demo-runner; do
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

CI uploads two artifact bundles on failure. Both are available from the
Actions run summary page under **Artifacts**.

### `two-actor-case-logs` (always uploaded)

Path in artifact: `devlogs/`

JSONL file layout:

```text
devlogs/two-actor/finder/<case-id-slug>-case-ledger.jsonl
devlogs/two-actor/vendor/<case-id-slug>-case-ledger.jsonl
devlogs/two-actor/case-actor/<case-id-slug>-case-ledger.jsonl
```

These are the replica files the invariant harness reads. Download and place
under the repo root `devlogs/` to re-run the harness locally against the CI
artifacts:

```bash
uv run pytest -m case_ledger_invariants -v --tb=short
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

### `demo-container-logs` (uploaded on failure only)

Path in artifact: `/tmp/demo-logs/`

Files: `combined.log`, `finder.log`, `vendor.log`, `coordinator.log`,
`case-actor.log`, `vendor2.log`, `demo-runner.log`.

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

## Ratchet Workflow Reference

When a fix lands that resolves an xfail invariant, see
`test/ci/README-case-log-ratchet.md` for the step-by-step process to
promote the test from `XFAIL` to a permanent regression guard.
