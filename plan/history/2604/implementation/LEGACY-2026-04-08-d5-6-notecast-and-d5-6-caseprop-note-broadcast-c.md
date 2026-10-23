---
title: "D5-6-NOTECAST and D5-6-CASEPROP \u2014 Note broadcast + case propagation\
  \ fix"
type: implementation
timestamp: '2026-04-08T00:00:00+00:00'
source: LEGACY-2026-04-08-d5-6-notecast-and-d5-6-caseprop-note-broadcast-c
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 4968
legacy_heading: "D5-6-NOTECAST and D5-6-CASEPROP \u2014 Note broadcast + case\
  \ propagation fix"
date_source: git-blame
---

## D5-6-NOTECAST and D5-6-CASEPROP — Note broadcast + case propagation fix

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:4968`
**Canonical date**: 2026-04-08 (git blame)
**Legacy heading**

```text
D5-6-NOTECAST and D5-6-CASEPROP — Note broadcast + case propagation fix
```

**Completed**: 2026-04-10
**Tasks**: D5-6-NOTECAST, D5-6-CASEPROP

### D5-6-NOTECAST — Broadcast notes to case participants

`AddNoteToCaseReceivedUseCase` now broadcasts an `AddNoteToCaseActivity` to
all case participants (excluding the note author) after adding a note to a
case, satisfying CM-06-005. The CaseActor is located by `by_type("Service")`
filtered on `context == case_id`; recipients are derived from
`VulnerabilityCase.actor_participant_index`. The broadcast is created,
appended to the CaseActor's `outbox.items`, and queued via
`record_outbox_item` for delivery by `outbox_handler`.

The manual note-forwarding block in `vultron/demo/two_actor_demo.py`
(`vendor_replies_to_question`) has been removed — the CaseActor broadcast
now handles distribution automatically.

Three new tests cover: broadcast created, author excluded, graceful skip when
no CaseActor.

### D5-6-CASEPROP — EmitCreateCaseActivity now embeds full case + `to` field

`EmitCreateCaseActivity.update()` in `vultron/core/behaviors/case/nodes.py`
now reads the full `VulnerabilityCase` from the DataLayer, embeds it as
`object_`, and derives `to` from `actor_participant_index` (excluding the
actor itself). This aligns it with the reference `CreateCaseActivity` in
`vultron/core/behaviors/report/nodes.py`.

### Validation

- `uv run black vultron/ test/` → 463 files unchanged
- `uv run flake8 vultron/ test/` → no errors
- `uv run mypy` → no issues (466 source files)
- `uv run pyright` → 0 errors, 0 warnings
- `uv run pytest --tb=short 2>&1 | tail -5` → `1265 passed, 5581 subtests passed in 34.16s`
