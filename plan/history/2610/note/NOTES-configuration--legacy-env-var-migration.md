---
source: NOTES-configuration--legacy-env-var-migration
timestamp: '2026-10-02T16:20:18.711651+00:00'
title: Legacy env var migration
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered — no os.environ.get of LOG_LEVEL/VULTRON_BASE_URL/VULTRON_DB_URL remains in vultron/
**Superseded by:** vultron/config (get_config())

---

## Legacy env var migration

The following env var names were used in the codebase before this design
was adopted. They MUST be replaced everywhere:

| Old name | New name |
|----------|----------|
| `LOG_LEVEL` | `VULTRON_SERVER__LOG_LEVEL` |
| `VULTRON_BASE_URL` | `VULTRON_SERVER__BASE_URL` |
| `VULTRON_DB_URL` | `VULTRON_DATABASE__DB_URL` |

`SeedConfig`-specific env vars (`VULTRON_ACTOR_NAME`, `VULTRON_ACTOR_TYPE`,
`VULTRON_ACTOR_ID`, `VULTRON_SEED_CONFIG`) are unchanged.

---
