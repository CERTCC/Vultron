---
title: "Priority 471: Bug Fixes and Demo Polish — COMPLETE"
type: priority
timestamp: '2026-04-29T00:00:00+00:00'

source: Priority 471
---

## Priority 471: Bug Fixes and Demo Polish

All sub-issues resolved and TASK-EMDEFAULT.1 implemented.

| Issue | Fix |
|---|---|
| #378, #379 | BUG-471.1: AnnounceLogEntryActivity serialize_as_any + typed object_ override |
| #380 | BUG-471.4: actor_id normalization after resolve_actor() in case/actor triggers |
| #381 | BUG-471.5: _rehydrate_fields WARNING→DEBUG for expected INVITE→ANNOUNCE miss |
| #382, #386 | BUG-471.2: parser.py fix for Accept carrying inline Invite |
| #383, #384 | BUG-471.3: SvcAcceptEmbargoUseCase owner-gated EM vs. per-participant PEC |
| #385 | BUG-471.6: EngageCaseBT/DeferCaseBT failure reason via get_failure_reason() |
| #390 | BUG-471.7a: docker/README.md .env setup section |
| #391 | BUG-471.7b: DataLayer create/save/update INFO log lines |
| EP-04 | EMDEFAULT.1: InitializeDefaultEmbargoNode atomic PROPOSE+ACCEPT → EM.ACTIVE |
