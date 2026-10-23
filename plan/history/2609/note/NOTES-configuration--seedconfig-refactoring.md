---
source: NOTES-configuration--seedconfig-refactoring
timestamp: '2026-09-17T17:08:15.787727+00:00'
title: SeedConfig Refactoring
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** vultron/demo/seed_config.py:117

---

## SeedConfig Refactoring

`SeedConfig` in `vultron/demo/seed_config.py` MUST be migrated to
`pydantic-settings` `BaseSettings` (issue #1334). Key changes:

- Subclass `BaseSettings` instead of `BaseModel`
- Drop `from_env()` and `from_file()` classmethods — `BaseSettings` handles
  source merging automatically
- Keep `load()` only if `VULTRON_SEED_CONFIG` path override cannot be
  expressed as a `YamlConfigSource`; otherwise remove it
- `LocalActorConfig` MUST become a plain `BaseModel` carrying only bootstrap
  identity fields (`name`, `actor_type`, `id_`) — it MUST NOT extend
  `ActorConfig` (CFG-07-007). Actor policy fields (`auto_create_case`,
  `default_case_roles`) are now owned by `AppConfig.actor`
- `PeerActorConfig` stays as a plain `BaseModel` sub-model

---
