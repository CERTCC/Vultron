---
title: Sync Behavior Trees — Design Notes
status: active
description: >-
  Design decisions and implementation guidance for the three sync BTs:
  AnnounceLogEntryReceivedBT, RejectLogEntryReceivedBT, and CommitLogEntryBT.
  Covers case-actor vs non-case-actor branching, port injection pattern, and
  migration from procedural sync use-case code.
related_specs:
  - specs/sync-behavior-trees.yaml
  - specs/sync-log-replication.yaml
  - specs/behavior-tree-integration.yaml
  - specs/case-log-processing.yaml
related_notes:
  - notes/sync-log-replication.md
  - notes/bt-integration.md
  - notes/case-log-authority.md
  - notes/event-driven-control-flow.md
relevant_packages:
  - vultron/core/behaviors
  - vultron/core/use_cases/received
  - vultron/core/use_cases/triggers
  - vultron/core/ports
---

# Sync Behavior Trees — Design Notes

**Relates to**: `specs/sync-behavior-trees.yaml` (SBT-01 through SBT-05),
`specs/sync-log-replication.yaml`, `specs/behavior-tree-integration.yaml`

**Source ideas**: IDEA-26050402 (case-actor vs non-case-actor log entry
handling), IDEA-26050403 (sync behavior tree design)

---

## Overview

Sync log-entry protocol flows are currently implemented as procedural use-case
code in `received/sync.py` and `triggers/sync.py`. These files violate
BT-06-001 (all protocol-significant behavior MUST be in BTs) and BT-06-005
(cascades as BT subtrees, not procedural calls).

This note captures the design decisions and BT structure needed to bring sync
into compliance, and introduces the case-actor vs non-case-actor branching
distinction that the current code treats uniformly.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| One or multiple BTs? | Three separate BTs | Preserves one-message-type-per-use-case pattern |
| Case-actor branch in AnnounceReceivedBT? | Yes — explicit branch | Case-actor receiving own entry is delivery round-trip, not replica update |
| Delivery confirmation tracking? | Deferred | Keeps scope tight; no `delivered` field needed yet |
| Case-actor no-op on valid round-trip? | Log DEBUG + return SUCCESS | Noisy but detectable; not a state update |
| Sender verification check? | Actor-ID comparison now | Simple, correct at prototype stage; seam for future crypto |
| Logging level for injection attempts? | WARNING | Protocol-significant but not a system failure |
| Hash-chain validation for non-case-actor? | MUST validate | Prevents spoofed log entries from corrupting replica state |
| CommitLogEntryBT trigger call? | Replace with BT subtree | Core MUST NOT call trigger functions; triggers are external API |
| Port injection method? | Blackboard context via BTBridge | Consistent with DataLayer pattern; keeps nodes decoupled |
| Spec RFC keywords? | MUST throughout | Prototype mode: no half-way implementations |

---

## Three BTs and Their Structures

### 1. AnnounceLogEntryReceivedBT

Handles inbound `Announce(CaseLogEntry)`. Root is a Selector with an
identity-check branch at the top — if the receiving actor is the case-actor,
take the case-actor subtree; otherwise take the participant subtree.

```text
AnnounceLogEntryReceivedBT (Selector)
├─ CaseActorSubtree (Sequence)            # early-exit if this actor IS the case-actor
│  ├─ CheckIsOwnCaseActor                 # Condition: am I the case-actor for this case?
│  ├─ VerifySenderIsOwnId                 # Condition: sender == my actor_id?
│  │   └─ [on FAILURE: log WARNING, return FAILURE to outer Selector]
│  └─ LogDeliveryConfirmation             # Action: log DEBUG, return SUCCESS
│
└─ ParticipantSubtree (Selector)          # taken if NOT the case-actor
   ├─ CheckLogEntryAlreadyStored          # Condition: idempotency guard (SYNC-03-003)
   └─ ValidateAndPersistFlow (Sequence)
      ├─ ReconstructChainTail             # Action: populate tail_hash, tail_index on blackboard
      ├─ CheckHashChainMatch              # Condition: prev_log_hash == tail_hash
      │   └─ [on FAILURE: SendRejectLogEntry action]
      └─ PersistLogEntry                  # Action: save VultronCaseLogEntry to DataLayer
```

**Notes**:

- The outer Selector means: try the case-actor path first. If I am not the
  case-actor, `CheckIsOwnCaseActor` fails and falls through to the participant
  path.
- `VerifySenderIsOwnId` failure logs WARNING and propagates FAILURE upward.
  A WARNING here signals a potential injection attempt.
- `CheckHashChainMatch` failure MUST trigger a `SendRejectLogEntry` action
  (a Fallback node wrapping the condition and the reject action, or handled
  by the Sequence failing and a sibling action in a parent Fallback).

### 2. RejectLogEntryReceivedBT

Handles inbound `Reject(CaseLogEntry)`. Triggered when a peer rejects an
announced entry due to hash-chain divergence.

```text
RejectLogEntryReceivedBT (Sequence)
├─ FindCaseActor          # Action: resolve case-actor ID for this case
├─ UpdateReplicationState # Action: upsert VultronReplicationState with last-accepted hash
└─ ReplayMissingEntries   # Action: fan-out Announce activities from last-accepted hash forward
```

**Notes**:

- `ReplayMissingEntries` queries the DataLayer for all log entries with
  `log_index > index_of(last_accepted_hash)` and queues one
  `Announce(CaseLogEntry)` per entry per recipient via SyncActivityPort.
- The case-actor ID resolved in `FindCaseActor` is used as the sender for
  replayed announces.

### 3. CommitLogEntryBT

Used by protocol flows (e.g., case creation, note attachment) that need to
commit a new log entry and fan it out to participants. Replaces the procedural
`commit_log_entry_trigger()` call inside `CommitCaseLogEntryNode`.

```text
CommitLogEntryBT (Sequence)
├─ ReconstructChainTail   # Action: tail_hash, tail_index from DataLayer
├─ CreateLogEntry         # Action: build VultronCaseLogEntry with computed entry_hash
├─ PersistLogEntry        # Action: save to DataLayer (commit point)
└─ FanOutLogEntry         # Action: Announce to all case participants via SyncActivityPort
```

**Notes**:

- `PersistLogEntry` is the commit point. `FanOutLogEntry` MUST only execute
  after `PersistLogEntry` succeeds (Sequence enforces this).
- This tree is not invoked as a standalone use case; it is composed as a
  subtree within other BTs (e.g., at the end of `CreateCaseBT`).
- `CommitCaseLogEntryNode` in `case/nodes.py` MUST be refactored to invoke
  this subtree instead of calling `commit_log_entry_trigger()`.

---

## Case-Actor vs Non-Case-Actor Distinction

The current `AnnounceLogEntryReceivedUseCase` treats all receiving actors
identically. This is incorrect:

| Actor type | Semantics of received `Announce(CaseLogEntry)` |
|---|---|
| Non-case-actor (participant) | State update: replicate entry into local replica |
| Case-actor (own entry round-tripped) | Delivery confirmation: entry already committed |

The case-actor committed the entry before announcing it. Receiving it back via
outbox→inbox is delivery confirmation only. Re-validating the hash chain and
re-persisting would be redundant and potentially incorrect if the local log
has advanced since the entry was sent.

**Caution**: A third-party actor could attempt to inject a log entry with the
case-actor's ID in the `actor` field. The sender verification node guards
against this at prototype stage (actor-ID comparison). In a production
implementation, cryptographic signature verification replaces this node
without restructuring the tree (SBT-02-005).

---

## Port Injection via Blackboard (General Pattern)

This is a cross-cutting architectural pattern applicable to all sync BTs and
any future BT-based protocol flow that needs a driven port.

**Rule**: All driven ports MUST be injected via the BTBridge blackboard
context. BT nodes MUST read ports from the blackboard at `update()` time.
BT nodes MUST NOT construct or acquire ports themselves.

**Why**: Keeps BT nodes decoupled from adapter construction. Mirrors the
existing `datalayer` blackboard key convention. Enables clean testing by
substituting mock ports via blackboard setup.

**How** — in the use case / handler:

```python
bridge = BTBridge(datalayer=dl)
tree = create_announce_log_entry_tree()
result = bridge.execute_with_setup(
    tree=tree,
    actor_id=actor_id,
    activity=event.activity,
    context_data={
        "sync_port": sync_port,   # injected here
    },
)
```

**How** — in a BT node:

```python
class PersistLogEntry(DataLayerAction):
    def update(self) -> Status:
        dl = self.blackboard["datalayer"]      # already established key
        sync_port = self.blackboard["sync_port"]  # injected port
        entry = self.blackboard["log_entry"]
        ...
```

**Blackboard key inventory for sync BTs**:

| Key | Type | Purpose |
|---|---|---|
| `datalayer` | `DataLayer` | Existing convention |
| `sync_port` | `SyncActivityPort` | Outbound activity queuing |
| `log_entry` | `VultronCaseLogEntry` | Entry being processed or created |
| `tail_hash` | `str` | Current chain tail hash |
| `tail_index` | `int` | Current chain tail log_index |
| `peer_id` | `str` | Actor ID of rejecting peer |
| `last_accepted_hash` | `str` | Last-accepted hash from rejection message |

---

## Migration Guide: Procedural → BT

### Step 1 — Create `vultron/core/behaviors/sync/`

```text
vultron/core/behaviors/sync/
    __init__.py
    nodes.py           # DataLayerCondition and DataLayerAction subclasses
    announce_tree.py   # create_announce_log_entry_tree()
    reject_tree.py     # create_reject_log_entry_tree()
    commit_tree.py     # create_commit_log_entry_tree()
```

### Step 2 — Port condition and action logic from use cases to nodes

Map existing procedural functions to BT nodes:

| Existing code | Target BT node |
|---|---|
| `_reconstruct_tail_hash()` | `ReconstructChainTailNode` (Action) |
| Hash-match comparison | `CheckHashChainMatchNode` (Condition) |
| Duplicate entry check | `CheckLogEntryAlreadyStoredNode` (Condition) |
| `dl.save(entry)` call | `PersistLogEntryNode` (Action) |
| `sync_port.send_reject_log_entry()` | `SendRejectLogEntryNode` (Action) |
| `_fan_out_log_entry()` | `FanOutLogEntryNode` (Action) |
| `_update_replication_state()` | `UpdateReplicationStateNode` (Action) |
| Entry-finding loop in replay | `ReplayMissingEntriesNode` (Action) |

### Step 3 — Wire use cases to BTs via BTBridge

Replace the procedural body of each use case's `execute()` method with
a `BTBridge.execute_with_setup()` call, injecting `sync_port` in
`context_data`.

### Step 4 — Refactor `CommitCaseLogEntryNode`

Change `CommitCaseLogEntryNode.update()` to compose and execute
`CommitLogEntryBT` as a subtree. Remove the direct call to
`commit_log_entry_trigger()`.

### Step 5 — Remove or demote trigger functions

`commit_log_entry_trigger()` and `replay_missing_entries_trigger()` in
`triggers/sync.py` are external API entry points (demo puppeteering).
After BT migration, they MUST NOT be called from core. If they are kept
for demo use, they should be moved to the demo trigger router
(see TASK-TRIGCLASS) and made to invoke the BTs via BTBridge rather than
duplicating logic.

---

## Testing Patterns

### BT node unit tests

Test each node in isolation using a mock blackboard and mock DataLayer:

```python
def test_check_hash_chain_match_success(mock_blackboard):
    mock_blackboard["tail_hash"] = "abc123"
    mock_blackboard["log_entry"] = entry_with_prev_hash("abc123")
    node = CheckHashChainMatchNode("check_hash")
    node.setup(timeout=0)
    status = node.update()
    assert status == Status.SUCCESS


def test_check_hash_chain_match_failure_logs_warning(mock_blackboard, caplog):
    mock_blackboard["tail_hash"] = "abc123"
    mock_blackboard["log_entry"] = entry_with_prev_hash("wrong_hash")
    node = CheckHashChainMatchNode("check_hash")
    node.setup(timeout=0)
    with caplog.at_level(logging.WARNING):
        status = node.update()
    assert status == Status.FAILURE
    assert "hash mismatch" in caplog.text.lower()
```

### BT tree integration tests

Test the full tree with a mock DataLayer and mock SyncActivityPort,
verifying that correct outbound activities are queued:

```python
def test_announce_received_participant_valid_entry(mock_dl, mock_sync_port):
    tree = create_announce_log_entry_tree()
    bridge = BTBridge(datalayer=mock_dl)
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id="https://example.org/participants/alice",
        activity=announce_activity_with_valid_chain(),
        context_data={"sync_port": mock_sync_port},
    )
    assert result.status == Status.SUCCESS
    mock_dl.save.assert_called_once()
    mock_sync_port.send_reject_log_entry.assert_not_called()
```

### Case-actor injection test

```python
def test_announce_received_case_actor_injection_attempt(mock_dl, caplog):
    tree = create_announce_log_entry_tree()
    bridge = BTBridge(datalayer=mock_dl)
    with caplog.at_level(logging.WARNING):
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id="https://example.org/actors/case-actor",
            activity=announce_with_spoofed_sender(),
            context_data={},
        )
    assert result.status == Status.FAILURE
    assert "WARNING" in caplog.text or any(
        r.levelname == "WARNING" for r in caplog.records
    )
    mock_dl.save.assert_not_called()
```

---

## Related

- `specs/sync-behavior-trees.yaml` — normative requirements (SBT-01–SBT-05)
- `specs/sync-log-replication.yaml` — SYNC-01–SYNC-09
- `specs/behavior-tree-integration.yaml` — BT-06-001, BT-06-005, BT-06-006
- `specs/case-log-processing.yaml` — CLP-01–CLP-05
- `notes/sync-log-replication.md` — hash-chain design, replication phases
- `notes/case-log-authority.md` — assertion vs canonical log entry model
- `notes/bt-integration.md` — BT execution model and design decisions
