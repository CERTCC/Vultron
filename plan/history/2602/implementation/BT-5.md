---
title: "BT-5 \u2014 Embargo Management + `establish_embargo` Demo"
type: implementation
timestamp: '2026-02-24T00:00:00+00:00'
source: BT-5
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 87
legacy_heading: "Phase BT-5 \u2014 Embargo Management + `establish_embargo`\
  \ Demo (COMPLETE 2026-02-23)"
date_source: git-blame
legacy_heading_dates:
- '2026-02-23'
---

## BT-5 — Embargo Management + `establish_embargo` Demo

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:87`
**Canonical date**: 2026-02-24 (git blame)
**Legacy heading**

```text
Phase BT-5 — Embargo Management + `establish_embargo` Demo (COMPLETE 2026-02-23)
```

**Legacy heading dates**: 2026-02-23

- All 7 embargo handlers: `create_embargo_event`, `add_embargo_event_to_case`,
  `remove_embargo_event_from_case`, `announce_embargo_event_to_case`,
  `invite_to_embargo_on_case`, `accept_invite_to_embargo_on_case`,
  `reject_invite_to_embargo_on_case`
- `establish_embargo_demo.py` (propose-accept and propose-reject paths) + dockerized
- Fixed `EmAcceptEmbargo` + `EmRejectEmbargo` `as_object` type to
  `EmProposeEmbargoRef`
