---
source: AF.8-10
timestamp: '2026-05-04T18:01:23.762274+00:00'
title: Factory return types are wire types, not domain models
type: learning
---

After migrating call sites in `vocab/examples/` and `demo/` from internal
activity classes to factory functions, 91 mypy/pyright type errors emerged.
Root cause: factory functions return base AS2 wire types (`as_Offer`,
`as_Create`, etc.) from `vultron.wire.as2.vocab.base.*`, but the migrated
code had `-> VultronActivity` return type annotations. `VultronActivity` is
a domain model (`vultron/core/models/`); it is NOT a supertype of `as_Offer`.

Key patterns and fixes:

- `vocab/examples/*.py`: change `-> VultronActivity` to the specific AS2 base
  type that the factory returns (e.g., `-> as_Offer`, `-> as_Accept`).
- `demo/utils.py#get_offer_from_datalayer`: return the `as_Offer` directly
  instead of wrapping it in `VultronActivity.model_validate(...)`.
- Demo scenario files: parse trigger endpoint responses as
  `as_Activity.model_validate(...)`, not `VultronActivity.model_validate(...)`.
- Pyright `[attr-defined]` errors on subtype-only attributes are fixed with
  a runtime `isinstance` assertion for type narrowing, not `# type: ignore`.

**Promoted**: 2026-05-04 — return-type principle already in
notes/activity-factories.md; `isinstance` narrowing tip added to AGENTS.md;
remainder archived as migration history.
