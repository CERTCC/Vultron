---
source: TASK-BTND5
timestamp: '2026-05-02T22:23:04.765398+00:00'
title: Generalize Participant BT Nodes (BTND5.2, BTND5.3)
type: implementation
---

## TASK-BTND5 — Generalize Participant BT Nodes (BTND5.2, BTND5.3)

Completed BTND5.2 and BTND5.3 (BTND5.1 was already done in a prior session).

### What was done

**BTND5.2a** — Created `vultron/core/models/actor_config.py` with `ActorConfig`
Pydantic model. `default_case_roles: list[CVDRoles]` defaults to `[]`.
Includes `field_serializer` and `field_validator` for CVDRoles (same pattern
as `VultronParticipant.case_roles`). Satisfies CFG-07-001, CFG-07-002.

**BTND5.2b** — Replaced `CreateInitialVendorParticipant` with
`CreateCaseOwnerParticipant` in `vultron/core/behaviors/case/nodes.py`.
New node accepts `actor_config: ActorConfig | None = None`. Effective roles =
`actor_config.default_case_roles + [CVDRoles.CASE_OWNER]` (order-preserving
dedup). When `actor_config` is `None`, participant receives only `CASE_OWNER`.
All other logic (report_id reuse, advance_to_accepted, initial_rm_state)
preserved. Satisfies BTND-05-002, CFG-07-004.

**BTND5.2c** — `LocalActorConfig` in `vultron/demo/seed_config.py` now
inherits from `ActorConfig`, gaining `default_case_roles` without duplicating
the field. Satisfies CFG-07-003.

**BTND5.2d** — Updated tree factories `create_create_case_tree` and
`create_receive_report_case_tree` to accept `actor_config: ActorConfig | None
= None` and pass it to `CreateCaseOwnerParticipant`. Satisfies CFG-07-004.

**BTND5.3** — Removed `CreateFinderParticipantNode` backward-compatibility
alias (had no callers in `vultron/`). Satisfies BTND-05-003.

### Tests

- `test/core/models/test_actor_config.py` (new): 11 tests covering ActorConfig
  defaults, CVDRoles parsing, serialization, round-trip, no-mutation, and
  LocalActorConfig composition.
- `test/core/behaviors/case/test_nodes.py`: Renamed
  `TestCreateInitialVendorParticipant` → `TestCreateCaseOwnerParticipant`;
  added role-config tests.
- `test/core/behaviors/case/test_create_tree.py`: Updated vendor-participant
  tests to check for CASE_OWNER; added actor_config integration test.
- `test/core/behaviors/case/test_receive_report_case_tree.py`: Updated two
  vendor-participant tests to check for CASE_OWNER.
- All 2212 unit tests pass (1 pre-existing flaky performance test excluded).

### Outcome

Hardcoded `CVDRoles.VENDOR` assumption removed from case-creation BT nodes.
Any CVD actor (vendor, coordinator, deployer) that receives a report and
creates a case will be correctly assigned `CASE_OWNER` plus whatever roles
are configured via `ActorConfig.default_case_roles`.
