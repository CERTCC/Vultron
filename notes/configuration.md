---
title: Configuration Management — Implementation Notes
status: active
kind: guidance
description: >
  Rules for YAML-backed Pydantic configuration in vultron/config/: layering,
  easily misread fields, and the test patterns that keep the process-wide
  config cache from leaking between tests.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/case-ledger-processing.yaml
  - specs/case-proposal.yaml
  - specs/case-shadow.yaml
  - specs/configuration.yaml
  - specs/embargo-policy.yaml
  - specs/vince-shadow-data.yaml
relevant_packages:
  - fastapi
  - pydantic
  - yaml
  - vultron/config
  - vultron/metadata
  - vultron/adapters
  - vultron/core
related_notes:
  - notes/case-ledger-authority.md
  - notes/case-proposal.md
  - notes/demo-interactive-ui.md
  - notes/embargo-default-semantics.md
  - notes/testing-pitfalls.md
  - notes/call-out-configuration.md
---

# Configuration Management — Implementation Notes

Requirements: `specs/configuration.yaml` (CFG). Code: `vultron/config/`
(`app.py` for `AppConfig`, `get_config()`, `reload_config()`,
`clear_config_cache()`, `config_override()`; `actor.py` for `ActorConfig`;
`ledger.py` for `LedgerConfig`; `vince.py` for `VinceConfig`; `secrets.py`
for the secret-setting rule). Field meanings and defaults live in those
modules' docstrings. The reader-facing list of every setting, its
`config.yaml` key and its `VULTRON_*` variable is
`docs/reference/configuration.md`, generated from `AppConfig` by
`vultron/metadata/docs/config_reference/`. A new field therefore needs an
`Attributes:` docstring entry or a `Field(description=...)`, or the strict docs
build fails.

## Design Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Scope | All app config unified | Replace scattered `os.environ.get()` calls |
| Config file name | `config.yaml` at project root | Simple; overridable via `VULTRON_CONFIG` |
| Precedence | Env vars override YAML | 12-factor app convention |
| Implementation | `pydantic-settings` `BaseSettings` | Native env-var support, custom sources |
| Sections | Production config only | Seed/demo config stays separate |
| Loading API | `get_config()` factory + `reload_config()` | Mirrors `get_datalayer()` pattern |
| Env var naming | `VULTRON_` prefix + `__` nesting | `VULTRON_SERVER__BASE_URL` → `server.base_url` |
| Defaults | All fields have defaults | Zero-config startup |
| Validation | Per-field only | Keep loading fast and simple |
| FastAPI | `Depends(get_config)` + direct calls | Consistent with DataLayer injection |

- In `settings_customise_sources`, the **first** source in the returned tuple
  wins (pydantic-settings 2.x), so `env_settings` comes before the YAML source.
- A `VULTRON_CONFIG` that names a missing file raises; an absent default
  `config.yaml` means "use defaults".
- The cache is owned by `functools.cache`, not a module global that
  `get_config()` rebinds (ruff `PLW0603`).

## Fields Whose Meaning Is Easy to Get Wrong

- **`ledger:` tolerances** govern a *claimed* `payloadSnapshot.published` at the
  CASE_MANAGER's commit boundary (CLP-14-009), not the commit stamp. Which
  timestamp each one governs is the load-bearing detail — see
  [notes/case-ledger-authority.md](case-ledger-authority.md) § "An Entry Has Two
  Timestamps, and They Belong to Different Layers". The skew tolerance is
  non-zero because participant and CASE_MANAGER clocks are not synchronised
  (ADR-0079).
- **`actor.case_actor_service_url`** has no default and MUST be supplied for
  any actor that may propose a case for a report it receives; without it
  `EnsureCaseActorHostedNode`, `ProposeReportCaseToActorNode` and
  `WritePendingReportCaseLinkNode` fail (CP-08-001, `notes/case-proposal.md`).
- **`actor.default_case_roles`** need not list `CASE_OWNER`; it is always
  appended at participant creation (BTND-05-002). A report receiver states these
  roles on its `Create(CaseProposal)` as `proposerCaseRoles`, and the CaseActor
  seats it with them; the CaseActor never reads its own `default_case_roles` for a
  proposer (CP-01-013, ADR-0133).
- **`actor.min_rsvp_window` / `default_rsvp_window`** are measured from the
  invite's `published` time and bounded by the embargo's end (EP-07-006); see
  [notes/embargo-default-semantics.md](embargo-default-semantics.md). Inbound
  extraction reads them through `_resolve_actor_config()` on both inbox paths;
  with no `ActorConfig` loaded, the protocol defaults apply.
- **`actor.protocol_default_embargo_duration`** is refused at load outside
  `[72 hours, 5 days]`. It never competes under shortest-wins and is not a
  minimum (EP-04-006, EP-04-007).
- **`actor.call_out_time_budget`** is read when a tree builds each call-out
  seam, not when a bundle is built, so a module-level bundle singleton still
  takes the configured value (BT-18-026). Positive only. The seam detects an
  overrun after the backend returns; it never interrupts it (BT-18-027).
- **A `SecretStr` field is environment-only** (so is `SecretBytes` or
  `Secret[X]`), and its type is the only declaration: the YAML source refuses
  a file that names its key, in any case and with any value, `null` included,
  and the reference page leaves it out of the example file (VSD-01-004,
  `vultron/config/secrets.py`). Declare it as `SecretStr` or
  `SecretStr | None` in a required section; any other shape is refused,
  because no single key path could be refused in a file.
- **`hide_input_in_errors` is set on `AppConfig` and on a secret's section.**
  Pydantic takes it from the outermost model being validated, so the section's
  setting alone would not stop `vince: <token>` being quoted (VSD-01-005). It
  hides only the input pydantic appends; a validator message that quotes its
  value (`got: {v!r}`) must never be written for a secret. Hand a secret on as
  `SecretStr` and unwrap it only where the request is built. No `.env` file or
  secrets directory is read.
- **`docker/seed-configs/`** `local_actor:` blocks carry bootstrap identity only
  (`name`, `actor_type`, `id`); actor policy belongs in the `config.yaml`
  `actor:` section.

## Layer Rules

`vultron/config/` is a **neutral** sub-package alongside `vultron/errors.py`
(CFG-07-006). Adapters and core may import it; it MUST NOT import
from `vultron/adapters/`, `vultron/wire/`, `vultron/core/`, or FastAPI.
`actor.py` takes `CVDRole` from `vultron/enums/roles.py`, which is bottom of the
stack and imports neither core nor config.

## Testing Pattern

- **Use `config_override(**env)`** when a test overrides `AppConfig` values
  (CFG-06-006). It patches `os.environ`, reloads the cache, and restores both on
  exit even when the body raises, so teardown ordering is correct by
  construction.
- **To only reset the cache, call `clear_config_cache()`**, never
  `reload_config()`, in teardown.
- **The ordering footgun (CFG-06-009):** the cache is process-wide, and
  `reload_config()` re-reads `os.environ` at once. `monkeypatch` undoes env
  changes *after* the teardown body runs, so `reload_config()` in teardown
  caches the test's patched values for every later test. Outside
  `config_override()`, undo the patches first, then reload. In the demo suite a
  leak shows up as order-dependent "no routable recipients" failures (#2086).
  `restore_case_actor_url_after_each_test` in `test/demo/conftest.py` repairs
  function-scoped leaks only; module-, class-, and session-scoped fixtures must
  order correctly themselves.
- **A test that needs a `VULTRON_*` setting MUST set it itself**, in its own
  module's autouse fixture. Fixing a leak removes config downstream tests were
  silently borrowing; a module that passes only in a full-suite run is
  order-dependent, not passing, so verify with a targeted run (#1897).
- **Unexpected demo drops warn.** `InProcessRouter.emit` in
  `vultron/demo/in_process.py` drops a delivery to an unregistered host at DEBUG only
  when the host is in `_KNOWN_FICTIONAL_HOSTS` (for example `vultron.example`);
  any other unregistered host logs WARNING, since it is almost always a config
  leak. Add a fictional host to the allowlist rather than silencing the warning.
