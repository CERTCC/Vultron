---
title: 'BUG-26042204 fixed: three-actor embargo activation flow'
type: implementation
timestamp: '2026-04-22T00:00:00+00:00'
source: LEGACY-2026-04-22-bug-26042204-fixed-three-actor-embargo-activatio
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7774
legacy_heading: "2026-04-22 \u2014 BUG-26042204 fixed: three-actor embargo\
  \ activation flow"
date_source: git-blame
legacy_heading_dates:
- '2026-04-22'
---

## BUG-26042204 fixed: three-actor embargo activation flow

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7774`
**Canonical date**: 2026-04-22 (git blame)
**Legacy heading**

```text
2026-04-22 — BUG-26042204 fixed: three-actor embargo activation flow
```

**Legacy heading dates**: 2026-04-22

- Issue: the three-actor demo left the authoritative case embargo in
  `EM.PROPOSED` because only the finder and vendor accepted the embargo
  proposal.
- Root cause: after owner-gated embargo activation landed, only the case owner
  can drive the shared case EM transition to `ACTIVE`; the coordinator-created
  case never had the coordinator accept the proposal.
- Resolution: updated `vultron/demo/scenario/three_actor_demo.py` so the
  coordinator accepts the embargo proposal on the authoritative CaseActor
  before the other participant accepts are recorded, and tightened final-state
  verification so all three participants, including the coordinator owner,
  must record acceptance of the active embargo.
