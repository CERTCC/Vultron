---
title: "AF.3–AF.6 — Case, Embargo, Participant, Actor, Sync factory modules"
type: implementation
date: 2026-04-30
source: TASK-AF-3to6
---

## TASK-AF AF.3–AF.6 — Activity Factory Modules

Implemented factory modules for all remaining domain areas as part of
TASK-AF (Activity Factory Functions).

### Completed

- **AF.3** `vultron/wire/as2/factories/case.py` — 16 factory functions
- **AF.4** `vultron/wire/as2/factories/embargo.py` — 8 factory functions
- **AF.5** `vultron/wire/as2/factories/case_participant.py` — 5 functions
- **AF.6** `vultron/wire/as2/factories/actor.py` (3) and
  `vultron/wire/as2/factories/sync.py` (2)
- Updated `vultron/wire/as2/factories/__init__.py` — 34 functions re-exported
- 5 test files, 170 new tests; full suite: 2180 passed, 12 skipped

### Key Design Notes

- `actor` is required on all AS2 activity classes; test fixtures must pass
  `actor=_ACTOR_URI` explicitly.
- Renamed `actor` param to `invitee`/`recommended` in two factories to avoid
  collision with the AS2 `actor` field passed via `**kwargs`.
- `rm_invite_to_case_activity` target type narrowed to
  `VulnerabilityCaseStub | str | None` to satisfy mypy/pyright.
- `ChoosePreferredEmbargoActivity`: intransitive (as_Question); named
  `any_of`/`one_of` params per AF-01-003; tests cast return to subtype to
  access those attributes.
- `RemoveEmbargoFromCaseActivity` uses `origin` not `target` per AS2 Remove.
- All factory functions log WARNING before raising
  VultronActivityConstructionError per AF-04-003.
