---
source: NOTES-case-communication-model--bt-implementation-guidance
timestamp: '2026-10-12T19:38:23.350034+00:00'
title: BT Implementation Guidance
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered plan; sender-side trigger use cases build and tick BTs (e.g. SvcAddNoteToCaseUseCase._build_tree)
**Superseded by:** vultron/core/use_cases/triggers/; notes/case-communication-model.md § Implementation: Resolving the CASE_MANAGER ID

---

## BT Implementation Guidance

Sender-side trigger use cases (`SvcAddNoteToCaseUseCase`,
`SvcAddParticipantStatusUseCase`, embargo triggers, etc.) currently contain
routing logic and activity-construction code that belongs in Behavior Trees.
The correct architecture:

```text
TriggerUseCase.execute()
  └── Sets blackboard context (actor_id, case_id, payload)
  └── Ticks BT

SenderBT (Sequence)
  ├── ResolveCaseManagerNode      # looks up CASE_MANAGER actor ID
  ├── ConstructActivityNode       # builds the AS2 activity addressed to CASE_MANAGER
  └── QueueToOutboxNode           # adds to actor outbox
```

Until BTs are implemented, the interim fix is to ensure all trigger use
cases use `_resolve_case_manager_id()` instead of a roster-wide list as
the recipient when building outbound participant activities.
