---
source: TASK-DL-REHYDRATE
timestamp: '2026-05-04T20:13:55.476296+00:00'
title: Migrate core use-cases from by_type/model_validate to typed list_objects
type: implementation
---

Migrated core use-cases from raw by_type()/model_validate() to typed list_objects() on CasePersistence.

Key changes:

- Added list_objects() to CasePersistence port
- Fixed EmbargoEvent.type_ from 'Event' to 'EmbargoEvent'; registered in VOCABULARY
- Added AOtype.EVENT subtype-aware isinstance matching in extractor (ActivityPattern.match)
- Updated extractor's object dispatch to use isinstance(obj, as_Event) instead of string comparison
- Migrated 4 model_validate() coercion sites:
  - received/sync.py: _reconstruct_tail_hash uses list_objects('CaseLogEntry')
  - triggers/sync.py: replay_missing_entries_trigger uses list_objects('CaseLogEntry')
  - triggers/embargo.py: _coerce_embargo_event simplified (no model_validate; dl.read returns typed EmbargoEvent)
  - behaviors/case/nodes.py: CaseParticipant.model_validate replaced with dl.read() + isinstance
- Updated SyncActivityPort and SyncActivityAdapter to accept LogEntryModel protocol
- Fixed find_embargo_proposal() to match EmbargoEvent by type_ in ('Event', 'EmbargoEvent')
- Updated tests: test_sync.py, test_embargo.py, test_base.py
