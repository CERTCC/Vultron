---
source: ISSUE-1342
timestamp: '2026-07-14T20:08:32.770970+00:00'
title: move CVDRole to vultron/enums/; config.py → config/ sub-package
type: implementation
---

## Issue #1342 — refactor: move CVDRole to vultron/enums/; config.py → config/ sub-package

Moved `CVDRole`, `serialize_roles`, `validate_roles` from `vultron/core/states/roles.py` to the new bottom-of-stack `vultron/enums/` package. Converted `vultron/config.py` into a `vultron/config/` sub-package with `app.py` (AppConfig etc.) and `actor.py` (ActorConfig). AppConfig gains `actor: ActorConfig` field. All ~99 CVDRole import sites and ~15 ActorConfig import sites updated. Deleted source files with no shims.

Code review found and fixed: stale `load_actor_config()` reference in AGENTS.md, stale testing-pattern snippet in notes/configuration.md, stale CVDRole import path in notes/case-communication-model.md, missing VULTRON_ACTOR__* env var clearance in test_config.py fixture, zero AppConfig.actor test coverage, silent-swallow bug in validate_roles (now raises for non-None non-list), dead helpers in test_enums_import_graph.py refactored to shared helper.

PR: <https://github.com/CERTCC/Vultron/pull/1432>
