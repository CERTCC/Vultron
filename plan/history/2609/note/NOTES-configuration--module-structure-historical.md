---
source: NOTES-configuration--module-structure-historical
timestamp: '2026-09-01T22:01:46.353972+00:00'
title: 'Historical: flat vultron/config.py module structure'
type: note
---

Archived from `notes/configuration.md` § "Module Structure (historical —
superseded by issue #1342)".

Removed from `notes/` because the layout no longer exists and notes/ states
current understanding only; the live layout is § "Current Architecture:
`vultron/config/` Sub-Package". The neutral-module constraint the section carried
was kept there rather than archived. Original text:

> The layout below was the pre-migration design. The flat `vultron/config.py` no
> longer exists.
>
> ```text
> vultron/
>   config.py          ← AppConfig, ServerConfig, DatabaseConfig,
>                         get_config(), reload_config()
>   demo/
>     seed_config.py   ← SeedConfig (separate; refactored to BaseSettings)
> ```
>
> `vultron/config.py` was a **neutral module** — it MUST NOT import from
> `vultron/adapters/` or `vultron/wire/` or FastAPI. It sat alongside
> `vultron/errors.py` as a shared-access layer. This constraint still applies to
> the `vultron/config/` sub-package.
