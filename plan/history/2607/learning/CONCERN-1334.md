---
source: CONCERN-1334
timestamp: '2026-07-10T18:20:37.482391+00:00'
title: SeedConfig imported from vultron/demo/ in production adapter (inbox_port_factories)
type: learning
---

## Background

PR #1331 resolved #1319 by wiring `_resolve_actor_config()` into the `SUBMIT_REPORT` dispatch path via `SeedConfig.load()`. This correctly honours `auto_create_case=False` at runtime.

However, the import lives in `vultron/adapters/driving/fastapi/inbox_port_factories.py` (a production adapter module):

```python
from vultron.demo.seed_config import SeedConfig
```

`notes/configuration.md` describes `SeedConfig` as a demo/seed-config concern separate from the production `AppConfig`. This import makes `vultron/demo/` a de-facto production dependency.

## What needs to be done

Move the actor configuration loading used by the production dispatch path to a neutral location — either:

- Promote `LocalActorConfig` / the `auto_create_case` field to `vultron/config.py` (or a new `vultron/actor_config.py` neutral module), or
- Add a thin accessor function in a neutral module that `inbox_port_factories.py` can import without touching `vultron/demo/`.

The resolution must preserve the existing env-var and YAML seed-config loading behaviour for demo deployments.

## References

- PR: <https://github.com/CERTCC/Vultron/pull/1331>
- Follows: #1319
- Notes: `notes/configuration.md` § "SeedConfig Refactoring Notes"
- Spec: `specs/configuration.yaml` CFG-07-*

**Resolved**: 2026-07-10 — implementation tracked in #1342, #1343.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1341>.
Spec: `specs/configuration.yaml` CFG-07-005 through CFG-07-007.
Notes: `notes/configuration.md` § "Target Architecture".
