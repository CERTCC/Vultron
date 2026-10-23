---
source: ISSUE-1343
timestamp: '2026-07-15T15:17:17.232553+00:00'
title: add load_actor_config() to vultron/config/; decouple LocalActorConfig
type: implementation
---

## Issue #1343 — refactor: add load_actor_config() to vultron/config/ and decouple SeedConfig from ActorConfig

Severed the production dependency on `vultron/demo/` introduced in PR #1331. Added `load_actor_config()` to the neutral `vultron/config/` layer, decoupled `LocalActorConfig` from `ActorConfig`, migrated `SeedConfig` to `BaseSettings`, and updated `inbox_port_factories.py` to use `load_actor_config()` instead of importing `SeedConfig`.

PR: <https://github.com/CERTCC/Vultron/pull/1441>
Defer issue: #1440 (wire load_actor_config through AppConfig.actor)
