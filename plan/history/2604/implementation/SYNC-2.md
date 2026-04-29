---
title: 'SYNC-2: One-way log replication (Announce(CaseLogEntry))'
type: implementation
date: '2026-04-11'
source: SYNC-2
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 5745
legacy_heading: 'SYNC-2: One-way log replication (Announce(CaseLogEntry))'
date_source: git-blame
---

## SYNC-2: One-way log replication (Announce(CaseLogEntry))

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:5745`
**Canonical date**: 2026-04-11 (git blame)
**Legacy heading**

```text
SYNC-2: One-way log replication (Announce(CaseLogEntry))
```

**Task**: Implement one-way log replication from CaseActor to Participant
Actors via `Announce(CaseLogEntry)` activities (Priority 330).

**Files created**:

- `vultron/core/models/case_log_entry.py` — `VultronCaseLogEntry(core.VultronObject)`
  with full hash-chain fields; auto-computes `id_` from `{case_id}/log/{log_index}`.
- `vultron/wire/as2/vocab/objects/case_log_entry.py` — re-exports core class
  and registers `VOCABULARY["CaseLogEntry"]` for DataLayer round-trips.
- `vultron/wire/as2/vocab/activities/sync.py` — `AnnounceLogEntryActivity(as_Announce)`
  with `object_: VultronCaseLogEntry | as_Link | str | None`.
- `vultron/core/models/events/sync.py` — `AnnounceLogEntryReceivedEvent`
  with `log_entry` property.
- `vultron/core/use_cases/received/sync.py` — `AnnounceLogEntryReceivedUseCase`
  (hash-chain validation, idempotency, persistence).
- `vultron/core/use_cases/triggers/sync.py` — `commit_log_entry_trigger()`
  (creates entry, fans out to participants).
- `test/core/use_cases/received/test_sync.py` — 9 tests (4 reconstruct-hash,
  5 use-case).

**Files modified**:

- `vultron/core/models/enums.py` — added `CASE_LOG_ENTRY = "CaseLogEntry"`.
- `vultron/core/models/events/base.py` — added `ANNOUNCE_CASE_LOG_ENTRY`.
- `vultron/core/models/events/__init__.py` — registered `AnnounceLogEntryReceivedEvent`.
- `vultron/core/models/protocols.py` — added `LogEntryModel` Protocol.
- `vultron/wire/as2/extractor.py` — added `AnnounceLogEntryPattern` and
  `_build_domain_kwargs` branch for `CASE_LOG_ENTRY`.
- `vultron/core/use_cases/use_case_map.py` — registered
  `AnnounceLogEntryReceivedUseCase`.
- `test/core/models/test_case_log.py` — fixed pre-existing mypy ignore code
  (`[assignment]` → `[index]`).

**Key design decision**: `VultronCaseLogEntry` extends `core.VultronObject`
(not `wire.VultronObject(as_Object)`) so it can be assigned to
`VultronEvent.object_: core.VultronObject`. Pydantic v2 accepts it in
`AnnounceLogEntryActivity.object_: VultronCaseLogEntry | as_Link | str | None`
since it is the first union member. `VOCABULARY["CaseLogEntry"]` is registered
manually (the `type_` value) since `core.VultronObject` does not trigger
`as_Base.__init_subclass__`.

**Validation**:

- `uv run black vultron/ test/ && uv run flake8 vultron/ test/` → clean
- `uv run mypy` → 0 errors (491 files)
- `uv run pyright` → 0 new errors (18 pre-existing in `test_note_trigger.py`)
- `uv run pytest --tb=short 2>&1 | tail -5` →
  `1510 passed, 11 skipped, 5581 subtests passed in 83.42s`
