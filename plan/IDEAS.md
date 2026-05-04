# Project Ideas

ID format: IDEA-YYMMDDNN

## IDEA-26050402 Case-actor vs non-case-actor log entry handling

When a non-case-actor receives `Announce(CaseLogEntry)`, it should treat the
log entry as an event that updates its local case replica. But when a
case-actor receives its own log entry (round-tripped outbox → inbox), the
semantics are different: the case-actor already committed the entry, so
receiving it back serves as **delivery confirmation**, not a state update.

Open questions:

- Should delivery confirmation be tracked? E.g., add a `delivered: bool`
  field to `VultronCaseLogEntry`, or track it in `VultronReplicationState`.
- When is `delivered` set — on outbox submit (optimistic) or on inbox
  round-trip receipt (confirmed)?
- Does the case-actor's received use case need a branch for "this is my own
  entry coming back" vs "this is a peer's entry"? Currently
  `AnnounceLogEntryReceivedUseCase` treats all actors the same.
- How does this interact with the BT-based sync flow (see
  `BUILD_LEARNINGS.md` 2026-05-04 TASK-ARCHVIO)? The BT could have a
  condition node that checks "am I the case-actor for this case?" and
  branches accordingly.

## IDEA-26050403 Sync behavior tree for log entry protocol

The sync use cases (`AnnounceLogEntryReceivedUseCase`,
`RejectLogEntryReceivedUseCase`, and the trigger helpers) currently contain
procedural logic that should be expressed as behavior trees, consistent with
how other protocol flows (report, case, embargo) work.

Sketch:

- **Announce received BT**: Sequence → [ValidateHashChain → StoreEntry]
  with a Fallback that sends Reject on hash mismatch.
- **Reject received BT**: Sequence → [UpdateReplicationState →
  ReplayMissingEntries]. Replay uses driven port for outbound Announces.
- **Commit log entry BT**: Sequence → [AppendToChain → PersistEntry →
  FanOutToParticipants]. Fan-out uses driven port.

The `SyncActivityPort` (from TASK-ARCHVIO) provides the driven port that
BT leaf nodes would use for outbound activities.

Depends on: TASK-ARCHVIO completion, BT node design for sync operations.
