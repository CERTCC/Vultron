---
title: "BT-4 \u2014 Actor Invitation + `invite_actor` Demo"
type: implementation
date: '2026-02-24'
source: BT-4
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 77
legacy_heading: "Phase BT-4 \u2014 Actor Invitation + `invite_actor` Demo\
  \ (COMPLETE 2026-02-23)"
date_source: git-blame
legacy_heading_dates:
- '2026-02-23'
---

## BT-4 — Actor Invitation + `invite_actor` Demo

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:77`
**Canonical date**: 2026-02-24 (git blame)
**Legacy heading**

```text
Phase BT-4 — Actor Invitation + `invite_actor` Demo (COMPLETE 2026-02-23)
```

**Legacy heading dates**: 2026-02-23

- `invite_actor_to_case`, `accept_invite_actor_to_case`,
  `reject_invite_actor_to_case`, `remove_case_participant_from_case` handlers
- `invite_actor_demo.py` (accept + reject paths) + dockerized
- Fixed `RmInviteToCase` pattern: removed `object_=AOtype.ACTOR` (real actors
  have type "Organization"/"Person", not "Actor")
