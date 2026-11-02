---
source: NOTES-configuration--environment-variable-reference
timestamp: '2026-11-02T14:40:16.606927+00:00'
title: Environment Variable Reference
type: note
---

**Archived:** 2026-11-02
**Reason:** delivered — removed from notes/configuration.md in #4496 without an archive entry; the reader-facing page now carries this content, generated from AppConfig so it cannot drift (this section had already drifted: its `server.base_url` default lacked `/api/v2`)
**Superseded by:** docs/reference/configuration.md (vultron/metadata/docs/config_reference.py), issue #4171

---

## Environment Variable Reference

| Env var | Maps to | Default |
|---------|---------|---------|
| `VULTRON_CONFIG` | path to config.yaml | `config.yaml` |
| `VULTRON_SERVER__BASE_URL` | `server.base_url` | `http://localhost:7999` |
| `VULTRON_SERVER__LOG_LEVEL` | `server.log_level` | `INFO` |
| `VULTRON_SERVER__LEDGER_STREAM_POLL_SECONDS` | `server.ledger_stream_poll_seconds` | `0.25` |
| `VULTRON_DATABASE__DB_URL` | `database.db_url` | `sqlite:///vultron.db` |
| `VULTRON_ACTOR__AUTO_CREATE_CASE` | `actor.auto_create_case` | `true` |
| `VULTRON_ACTOR__DEFAULT_CASE_ROLES` | `actor.default_case_roles` | `[]` |
| `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL` | `actor.case_actor_service_url` | `None` |
| `VULTRON_ACTOR__PROTOCOL_DEFAULT_EMBARGO_DURATION` | `actor.protocol_default_embargo_duration` | `PT72H` |
| `VULTRON_LEDGER__CLOCK_SKEW_TOLERANCE_SECONDS` | `ledger.clock_skew_tolerance_seconds` | `300` |
| `VULTRON_LEDGER__FUTURE_TOLERANCE_SECONDS` | `ledger.future_tolerance_seconds` | `300` |
| `VULTRON_LEDGER__STALENESS_WINDOW_DAYS` | `ledger.staleness_window_days` | `7` |
