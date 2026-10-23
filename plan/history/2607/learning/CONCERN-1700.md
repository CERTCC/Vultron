---
source: CONCERN-1700
timestamp: '2026-07-27T19:44:11.674524+00:00'
title: CreateCaseActorServiceNode must write to case-actor container DataLayer not
  local
type: learning
---

## Problem

`CreateCaseActorServiceNode` (in `vultron/core/behaviors/case/nodes/case_setup.py`) calls `self.datalayer.create(case_actor)` — writing the `VultronCaseActor` record into the **local** DataLayer of whichever container is running the BT (vendor, coordinator, etc.).

This means that in the multi-container topology (`docker/docker-compose-multi-actor.yml`), with `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=http://case-actor:7999/api/v2` pointing at the dedicated case-actor container:

1. `ResolveCaseActorUrlsNode` derives IDs like `http://case-actor:7999/api/v2/actors/case-actor-{slug}` ✅ (correct URL)
2. `CreateCaseActorServiceNode` writes that record into the **vendor's** DataLayer ❌
3. Subsequent outbox deliveries addressed to `http://case-actor:7999/api/v2/actors/case-actor-{slug}/inbox/` get **404** because the case-actor container has no record of that actor

The CI Demo Integration jobs (all six scenarios) fail with `Client error '404 Not Found'` for all deliveries to the case-actor container.

### Root cause

`CreateCaseActorServiceNode` violates per-actor DataLayer isolation (ADR-0012): it writes a record that only belongs in the case-actor container's DataLayer. Previously masked because `ResolveCaseActorUrlsNode` derived IDs from `server_base_url` (the container's own URL). PR #1695 introduced the explicit `case_actor_service_url` config field, which made the mismatch visible.

`RegisterCaseActorParticipantNode` has the same issue.

### Resolution (2026-07-27)

Agreed fix: move actor-record creation to `create_case_proposal_received_tree` (case-actor side). The case-actor container creates its own `VultronCaseActor` and `VultronParticipant` records when handling `Create(as_CaseProposal)`. Causal ordering: VultronCaseActor record → VulnerabilityCase → persist both → emit Accept. Remove `CreateCaseActorServiceNode` and `RegisterCaseActorParticipantNode` from the vendor-side `CreateCaseActorNode` tree. This implements the intent of ADR-0023 (CaseProposal protocol) without needing a new ADR.

Key design decisions:

- No outbox queuing approach needed; case-actor handles everything synchronously on receipt of CaseProposal
- docker-compose: all four containers (finder, vendor, coordinator, actor5) get `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=http://case-actor:7999/api/v2`
- FV demo: remove `verify_case_actor_unused()`, add assertions that case-actor container holds expected records
- `notes/case-proposal.md` table row for `CreateCaseActorNode` is inaccurate and needs updating (deferred to impl issue AC-5)

Implementation tracked in #1733.

Resolved: 2026-07-27 — implementation tracked in #1733.
