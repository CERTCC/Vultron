---
title: "P347-BRIDGE \u2014 Extend outbox expansion bridge"
type: implementation
date: '2026-04-18'
source: P347-BRIDGE
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6762
legacy_heading: "P347-BRIDGE \u2014 Extend outbox expansion bridge (COMPLETE\
  \ 2026-05-22)"
date_source: git-blame
legacy_heading_dates:
- '2026-05-22'
---

## P347-BRIDGE — Extend outbox expansion bridge

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6762`
**Canonical date**: 2026-04-18 (git blame)
**Legacy heading**

```text
P347-BRIDGE — Extend outbox expansion bridge (COMPLETE 2026-05-22)
```

**Legacy heading dates**: 2026-05-22

**Task**: Extend the backward-compatibility expansion bridge in
`handle_outbox_item` from `("Create", "Announce")` to also include
`"Add"`, `"Invite"`, and `"Accept"` activity types. Added a TODO comment
noting that `"Join"` and `"Remove"` will need the same treatment when
implemented.

### Files Changed

- `vultron/adapters/driving/fastapi/outbox_handler.py`: Extended
  `activity_type in (...)` tuple; updated comment block; added TODO for
  `"Join"` and `"Remove"`.
- `test/adapters/driving/fastapi/test_outbox.py`: Added 6 new parametrized
  tests (3 expansion-success + 3 integrity-error-on-failure) covering
  `Add`, `Invite`, `Accept`; moved top-level imports (`pytest`,
  `VultronOutboxObjectIntegrityError`); added `_make_activity_with_bare_object`
  helper.

### Test Result

1625 passed, 12 skipped, 182 deselected, 5581 subtests passed
