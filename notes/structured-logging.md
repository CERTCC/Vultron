---
title: Structured Logging — Narrative Standard and Infrastructure Demotion Guide
status: active
tags: [logging, observability, debugging]
description: >
  Narrative log template (SL-04-006), infrastructure demotion list (SL-04-007),
  and per-module guidance for keeping INFO logs readable as a CVD protocol story.
related_specs:
  - specs/structured-logging.yaml
related_notes:
  - notes/codebase-structure.md
  - notes/bt-integration.md
---

# Structured Logging — Narrative Standard and Infrastructure Demotion Guide

## Motivation

Actor container INFO logs serve two audiences simultaneously: developers
debugging a live run, and contributors reading a CI transcript to verify
protocol correctness. Both audiences need the INFO log to read as a coherent
story of what the protocol did — not a stream of persistence bookkeeping.

The underlying requirement is SL-04-001: all state transitions MUST be logged
at INFO. The concrete gap is that many state transitions are only visible at
DEBUG (or not at all), while the INFO channel is dominated by infrastructure
noise.

---

## Narrative Template (SL-04-006)

All BT leaf nodes and service-layer methods that write a protocol-visible state
change SHOULD emit an INFO log following this template:

```text
Actor '<actor_id>' <verb> '<object_id>' (<STATE_A> → <STATE_B>)
```

### Approved verbs by domain

| Domain | Verb | Example |
|---|---|---|
| RM | `RM:` | `Actor 'finder' RM: RECEIVED → ACCEPTED for case 'case-uuid'` |
| CS/VFD | `CS:` | `Actor 'vendor' CS: vfd → Vfd (fix ready) for case 'case-uuid'` |
| CS/VFD | `CS:` | `Actor 'vendor' CS: Vfd → VFd (fix deployed) for case 'case-uuid'` |
| CS/PXA | `CS:` | `Actor 'finder' CS: pxa → Pxa (publicly known) for case 'case-uuid'` |
| EM | `embargo:` | `Actor 'finder' proposed embargo 'embargo-uuid' (EM NONE → PROPOSED)` |
| EM | `embargo:` | `Actor 'finder' embargo PROPOSED → ACTIVE for case 'case-uuid'` |
| EM | `embargo:` | `Actor 'finder' embargo ACTIVE → TERMINATED for case 'case-uuid'` |
| Case | `case:` | `Actor 'finder' engaged case 'case-uuid' (RM VALID → ACCEPTED)` |
| Invite | `invite:` | `Actor 'finder' received case invite for 'case-uuid' from 'coordinator'` |
| BT failure | `BT:` | `Actor 'vendor' BT execution FAILURE for case 'case-uuid': <reason>` |

The existing embargo-propose messages (`Actor X proposed embargo Y (EM NONE → PROPOSED)`)
and demo-step emoji markers (`demo_step` / `demo_check`) already follow this
pattern and MUST NOT be changed.

---

## Infrastructure Patterns to Demote to DEBUG (SL-04-007)

The following patterns appeared at INFO as of the concern CONCERN-1968. Each
MUST be at DEBUG or lower. Verify with a grep after any bulk refactor.

| Pattern | File(s) | Why DEBUG |
|---|---|---|
| `BT structure:\n<tree>` (before every execution) | `vultron/core/behaviors/bridge.py:209` | BT scaffolding, not story |
| `DataLayer stored/saved/updated X 'ID'` | `vultron/adapters/driven/datalayer_sqlite/crud.py:70,152,195,301` | Persistence internals; higher-level "Created X" messages above them are fine |
| `Parsing activity from request body` / `Parsing activity from body` | `vultron/adapters/driving/fastapi/routers/actors/_inbox.py:62`, `vultron/wire/as2/parser.py:113` | HTTP handler internals; duplicate pair |
| `Processing outbox for actor ...` | `vultron/adapters/driving/fastapi/outbox_handler.py:242` | Preamble; delivery result is the meaningful line |
| `Dispatch: dispatched X activity_id=...` / `process_payload: outcome status=processed` / `run_inbox_pipeline: status=processed` | `vultron/core/behaviors/inbox/_process_payload.py:214`, `vultron/adapters/driving/fastapi/inbox_orchestration.py:370,386` | Mechanical pipeline completion repeats |
| `EM FSM: Finished processing state X exit/enter callbacks` | `vultron/core/states/em.py` (transitions callback) | FSM internals; the `Actor X proposed embargo Y (EM A → B)` already captures this |
| `sync adapter: queued Announce(CaseLedgerEntry) 'UUID' → ['actor']` | `vultron/adapters/driven/sync_activity_adapter.py:116` | Fires per recipient per entry |
| `store_embedded_participants: stored participant 'UUID'` | `vultron/core/use_cases/received/case/_helpers.py:92` | Fires per participant on every case announcement |
| `SeedAnnouncedCaseNode: case already exists locally — skipping save` | `vultron/core/behaviors/case/nodes/announce.py:78` | Routine idempotency skip |
| `Activity UUID already received by actor; ignoring duplicate submission` | `vultron/adapters/driving/fastapi/routers/actors/_routes.py:365` | Normal sync protocol behaviour |
| `discover_actors()` full actor JSON at INFO | `vultron/demo/utils.py:280,283,286` | Only the ID is useful; full dump → DEBUG |

---

## Missing INFO Messages to Add (SL-04-001 violations)

These state transitions happened with no INFO output as of CONCERN-1968.

| Domain | Message to add | Location |
|---|---|---|
| RM per-participant | `Actor '<id>' RM: <A> → <B> for case '<case_id>'` | BT nodes that write `ParticipantStatus` with a new RM state |
| CS/VFD | `Actor '<id>' CS: <vfd_before> → <vfd_after> (<event>) for case '<case_id>'` | BT nodes for fix-ready, fix-deployed |
| CS/PXA | `Actor '<id>' CS: <pxa_before> → <pxa_after> (<event>) for case '<case_id>'` | BT nodes for publish |
| Case engagement | `Actor '<id>' engaged case '<case_id>' (RM VALID → ACCEPTED)` | engage-case trigger BT |
| EM PROPOSED→ACTIVE | `Actor '<id>' embargo PROPOSED → ACTIVE for case '<case_id>'` | embargo-accept BT when all signatories have accepted |
| EM ACTIVE→TERMINATED | `Actor '<id>' embargo ACTIVE → TERMINATED for case '<case_id>'` | embargo-terminate BT |
| Invite receipt | `Actor '<id>' received case invite for '<case_id>' from '<sender>'` | received-invite use case / BT |
| BT FAILURE reason | `Actor '<id>' BT execution FAILURE for case '<case_id>': <reason>` | `BTBridge.execute_with_setup` (non-SUCCESS path) |

---

## Implementation Guidance

### Where to add new log lines

Add them in the **BT leaf node** that performs the state write, not in the
use-case `execute()` wrapper. This mirrors the existing embargo proposal
pattern (`AdvanceEMStateToProposedNode` etc.) and keeps protocol-significant
logging co-located with the protocol-significant action.

Use `self.logger.info(...)` (on `DataLayerAction`) or `logger.info(...)` from
a module-level logger. Include `actor_id` and `case_id` in every message.

### Grep check after refactor

After any bulk logging-level change, always run:

```bash
grep -rn "logger\.info.*DataLayer stored\|logger\.info.*DataLayer saved\|logger\.info.*BT structure\|logger\.info.*Processing outbox" vultron/
```

If any hits remain, they are regressions.

### `discover_actors()` — trim to ID only

```python
# Before
logger.info(f"Found finder actor: {logfmt(finder)}")
# After
logger.info("Found finder actor: %s", finder.get("id", "<unknown>"))
```

Full actor JSON (all fields) belongs at DEBUG.

---

## Relationship to SL specs

| Spec | Rule |
|---|---|
| SL-04-001 | All state transitions MUST be logged at INFO — the missing messages above violate this |
| SL-04-006 | Narrative template SHOULD; see table above |
| SL-04-007 | Infrastructure patterns MUST NOT be at INFO; see demotion list above |
