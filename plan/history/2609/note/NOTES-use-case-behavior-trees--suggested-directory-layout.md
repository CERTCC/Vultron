---
source: NOTES-use-case-behavior-trees--suggested-directory-layout
timestamp: '2026-09-17T17:32:56.671710+00:00'
title: Suggested Directory Layout
type: note
---

**Archived:** 2026-09-17
**Reason:** (e) misleading — proposed layout never adopted; contradicts real structure
**Superseded by:** actual: vultron/core/{ports,behaviors,use_cases,models}/

---

## Suggested Directory Layout

Example structure:

```text
core/

  domain/
      vulnerability_case.py
      embargo.py

  events/
      domain_events.py

  behavior/

      engine.py
      registry.py

      trees/
          embargo_invite_tree.py
          embargo_accept_tree.py
          publish_advisory_tree.py

      nodes/
          check_case_open.py
          check_duplicate_invite.py
          add_invitation.py
          notify_participants.py

application/

  use_cases/
      invite_actor_to_embargo.py
      accept_embargo_invitation.py
      publish_advisory.py
```

Guidelines:

* **domain/** contains aggregates and invariants
* **behavior/** contains policy logic
* **application/use_cases/** contains orchestration

---
