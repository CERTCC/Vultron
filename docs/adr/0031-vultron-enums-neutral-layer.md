---
status: accepted
date: 2026-07-10
deciders: Allen D. Householder
---

# Introduce `vultron/enums/` as a Bottom-of-Stack Neutral Layer for Cross-Cutting Enumerations

## Context and Problem Statement

`vultron/config/` must be a neutral module — it must not import from
`vultron/core/` or `vultron/adapters/`. However, `ActorConfig` (which will
live in `vultron/config/actor.py`) needs `CVDRole` to type the
`default_case_roles` field. `CVDRole` currently lives in
`vultron/core/states/roles.py`, which is inside the core domain layer.

If `vultron/config/` imports `CVDRole` from `vultron/core/`, it violates the
neutral-module constraint: neutral modules must not import from core. The
import graph has no valid location for `CVDRole` that satisfies all three
layers (core, config, adapters) simultaneously — unless a new bottom-of-stack
layer is introduced that all other layers may import freely.

Concern #1334 and spec CFG-07-006 identified this gap.

## Decision Drivers

- `vultron/config/` must remain neutral (no imports from `vultron/core/` or
  `vultron/adapters/`).
- `ActorConfig.default_case_roles` requires `CVDRole` at type-annotation time.
- `CVDRole` is a pure enumeration with no domain-logic dependencies — it is
  appropriate as a shared primitive.
- The fix must not create a circular import.
- The fix should generalise: other enumerations may need the same treatment.

## Considered Options

1. **Introduce `vultron/enums/` as a new bottom-of-stack neutral package**
   containing `CVDRole` and related helpers, importable by all layers.
2. **Move `CVDRole` into `vultron/config/`** directly, making it a config
   concern rather than a domain concern.
3. **Keep `CVDRole` in `vultron/core/` and use a `TYPE_CHECKING` guard** in
   `vultron/config/actor.py` to avoid the runtime import.
4. **Use `str` / plain string literals** for `default_case_roles`, deferring
   `CVDRole` validation to a later layer.

## Decision Outcome

Chosen option: **Introduce `vultron/enums/` as a new bottom-of-stack neutral
package**, because it is the only option that preserves both the neutral-module
constraint on `vultron/config/` and the domain-model status of `CVDRole` as a
shared primitive, without `TYPE_CHECKING` hacks or loss of type safety.

### Consequences

- Good, because `vultron/config/`, `vultron/core/`, and `vultron/adapters/`
  can all import from `vultron/enums/` freely without layering violations.
- Good, because `CVDRole` retains its identity as a domain primitive rather
  than being absorbed into config or stringly-typed.
- Good, because `vultron/enums/` can absorb other cross-cutting enumerations
  in the future (e.g., `RunMode`) following the same pattern.
- Bad, because it adds a new top-level package to the module hierarchy;
  existing imports of `CVDRole` from `vultron/core/states/roles.py` must be
  updated (tracked in #1342 / #1343).
- Bad, because `vultron/enums/` must be kept strictly free of imports from
  `vultron/core/`, `vultron/config/`, or `vultron/adapters/` — a new
  invariant to enforce.

## Pros and Cons of the Options

### Option 1 — `vultron/enums/` bottom-of-stack package

- Good, because it resolves the import cycle cleanly for all current and
  future neutral-module consumers.
- Good, because the constraint is enforceable via import-graph linting.
- Neutral, because the migration is mechanical (search-and-replace imports).

### Option 2 — Move `CVDRole` into `vultron/config/`

- Bad, because `CVDRole` is used by `vultron/core/` BT nodes; placing it in
  `vultron/config/` would make core depend on config — a layering violation.

### Option 3 — `TYPE_CHECKING` guard

- Bad, because it breaks runtime isinstance checks and Pydantic validators
  that need the actual enum class at import time.
- Bad, because `TYPE_CHECKING` guards are fragile; they hide dependency
  structure rather than resolving it.

### Option 4 — Plain strings

- Bad, because it removes the type safety that `CVDRole` provides.
- Bad, because it moves validation responsibility to runtime rather than
  model-construction time.

## Validation

Import-graph tests in `test/architecture/` (ARCH-01 series) must be extended
to assert:

- `vultron.enums` does NOT import from `vultron.core`, `vultron.config`, or
  `vultron.adapters`.
- `vultron.config` does NOT import from `vultron.core` or `vultron.adapters`.

## More Information

Generated spec requirements: `specs/configuration.yaml` CFG-07-006.

Related:

- Concern #1334 — original bug report (SeedConfig in production adapter)
- PR #1341 — docs: plan concern #1334 (this ADR drafted as follow-up)
- Issues #1342 / #1343 — implementation of the config sub-package
- `notes/configuration.md` § "Target Architecture" — full sub-package layout
  and import-graph constraints
