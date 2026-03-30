# Use Cases

This package contains the core use-case classes for the Vultron protocol.
Use cases are organized by role:

## Sub-packages

- **`received/`** — Use cases that process inbound received messages.
  Each class handles one `MessageSemantics` value and updates local
  state to reflect the sender's assertion.
- **`triggers/`** — Use cases implementing actor-initiated behaviors.
  Each class corresponds to a triggerable action that the local actor
  can perform (e.g., validate a report, propose an embargo).
- **`query/`** — Use cases implementing read-only queries over DataLayer
  state (e.g., compute valid CVD actions for an actor in a case).

## Information Flow

The trigger → received → sync information flow:

```text
Local Actor                    Remote Actor
     │                               │
     ▼                               │
triggers/           (outbound message sent)
     │ ──────────────────────────────▶ received/
     │                               │    │
     │                               │    ▼
     │                         State updated in
     │                         remote DataLayer
     │                               │
     ◀────────────── (sync replicates event log) ──
```

1. **Trigger** (`triggers/`): Local actor initiates an action (e.g.,
   validate a report). This emits an outbound ActivityStreams activity.
2. **Received** (`received/`): Remote actors receive the inbound activity
   and update their local state to reflect the sender's assertion.
3. **Sync** (future, `SYNC-1`/`SYNC-2`): The CaseActor replicates the
   resulting case event log to all participants via AS2 Announce activities.

## Package Root

The package root (`vultron/core/use_cases/`) contains only:

- `__init__.py` — Package declaration
- `use_case_map.py` — `USE_CASE_MAP`: authoritative `MessageSemantics` →
  use-case class routing table
- `_helpers.py` — Shared helper functions used across `received/` and
  `triggers/`
