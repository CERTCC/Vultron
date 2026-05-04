---
source: TASK-BTND5-4
timestamp: '2026-05-04T14:19:08.588357+00:00'
title: BTND5.4 — Refactor CVDRoles Flag to CVDRole StrEnum
type: implementation
---

## TASK-BTND5-4 — Refactor CVDRoles Flag to CVDRole StrEnum

### What was done

**CVDRole StrEnum** introduced in `vultron/core/states/roles.py`:

- `CVDRole(StrEnum)` with 7 atomic role members (FINDER, REPORTER, VENDOR,
  DEPLOYER, COORDINATOR, OTHER, CASE_OWNER); values are lowercase strings
  via `auto()` (e.g. `CVDRole.FINDER == 'finder'`).
- No `NO_ROLE` (empty list represents no role), no combination aliases.
- `serialize_roles(list[CVDRole]) -> list[str]`: emits `.value` (lowercase).
- `validate_roles(object) -> list[CVDRole]`: parses strings via
  `CVDRole(item.lower())`; accepts both enum members and string values.

**CVDRolesFlag** (legacy `bt/` simulator enum) moved to
`vultron/bt/roles/enums.py`:

- Renamed from `CVDRoles` to `CVDRolesFlag`; all combination aliases and
  `add_role()` preserved.
- `vultron/bt/states.py`, `bt/roles/conditions.py`,
  `bt/vul_discovery/behaviors.py`, `demo/vultrabot.py` all updated to
  import `CVDRolesFlag` from the new location.

**Core/wire migration** (all now use `CVDRole` + centralized helpers):

- `vultron/core/models/participant.py` (`VultronParticipant`)
- `vultron/core/models/actor_config.py` (`ActorConfig`)
- `vultron/wire/as2/vocab/objects/case_participant.py` (`CaseParticipant`
  and subclasses): removed `set_no_role_if_empty` model validator; empty list
  now represents no roles.
- `vultron/core/behaviors/case/nodes.py`,
  `receive_report_case_tree.py`, `create_tree.py`
- `vultron/core/states/__init__.py`: exports `CVDRole`, `serialize_roles`,
  `validate_roles`; drops `CVDRoles` and `add_role`.
- `vultron/core/use_cases/query/action_rules.py`: emits `.value` for roles.

**Serialization contract**: roles are now lowercase strings in JSON/DB
(e.g. `["finder", "vendor"]`).

**Tests**:

- `test/core/states/test_cvd_roles.py`: rewritten for `CVDRole` StrEnum
  with 19 tests covering values, lookup, serialize/validate roundtrip.
- `test/bt/roles/test_cvd_roles_flag.py` (new): legacy Flag enum tests
  migrated here.
- All other test files updated to import `CVDRole` and use `.value` in
  assertions where needed.

### Outcome

2236 tests pass. All four linters (Black, flake8, mypy, pyright) clean.
`CVDRoles` bitmask removed from core/wire layers. Persisted records now
store human-readable lowercase role strings.
