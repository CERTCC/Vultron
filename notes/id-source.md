---
title: The Id Minter Draws From an Id Source — Migration Plan
status: active
kind: plan
tracks:
  - "#5676"   # epic: a re-recorded scenario equals the committed one
  - "#6116"   # the recording harness through the port
description: >
  The rest of the migration to ADR-0185: the one object id minter draws from an
  id-source port, and the recording run still has to move from patching
  uuid.uuid4 to the scoped install.
related_specs:
  - specs/object-ids.yaml
  - specs/architecture.yaml
  - specs/demo-ci.yaml
---

# The Id Minter Draws From an Id Source — Migration Plan

ADR-0185 decides that the one minter, `new_object_id` (OID-01-004), draws from an
id-source port, and that a run needing repeatable ids installs its source for a
block (OID-01-011, OID-01-012). The minter draws from the port, and the
docs-example generator installs its source through it, but the recording run
still patches `uuid.uuid4` process-wide. This note holds the remaining work and
the rules each slice keeps.

A run installs its source with `install_id_source(source)`, a context manager in
`vultron.core.models._helpers`. The source is any callable that returns a
`uuid.UUID` (the `IdSource` Protocol), so `SeededUuid4` and `_ScopedIds` fit as
they are. A nested install raises `VultronIdSourceInstalledError`.

## Rules every slice keeps

- **Nothing patches the standard library's draw.** A reproducible run supplies
  its ids only through the scoped install, because a patch of `uuid.uuid4` also
  reaches py_trees and moves a recording's ids with the tree's shape.
- **Mint anywhere, but only through the minter.** Ids are not threaded to the
  act's edge: an id is a name with no value two reads must agree on, and the
  `id_` default factories run outside any tree run (OID-01-004; ADR-0185).
- **The application factory installs nothing.** The system source is the
  default, because `create_app()` must not change process-wide state
  (ARCH-16-001).
- **The port lives beside the minter, not in `vultron/core/ports/`.** Its
  Protocol, the system source and the scoped install sit in `vultron/core/models/`,
  because the docs-example generator in the wire layer supplies a source and the
  wire layer may not import `vultron.core.ports` (ARCH-22-001).
- **An install restores, and does not nest.** The previous source comes back on
  exit and on an exception; a second install inside an active one fails, because
  the two runs would silently share one stream of ids.
- **Exemptions shrink, never grow.** Each slice removes its own entry from
  `NON_ID_RANDOM_UUID_EXEMPTIONS` in the same PR, because the exact-set assert in
  `test_no_function_but_the_system_id_source_draws_a_random_uuid` fails on an entry
  that no longer draws (OID-01-004); the database-name entry stays, because that
  draw names no object.
- **A test that observes the minter through `uuid4` moves to the port.** A test
  that replaces or calls `uuid.uuid4` to watch the minter checks nothing once the
  minter draws from the id source, so the slice that changes the draw rewrites it.

## Remaining slice

- **Recordings** (#6116). `deterministic_run()` installs `SeededUuid4` through
  the port and drops its `sys.modules` sweep; every recording is regenerated
  once. `test/demo_unit/test_determinism.py` drops its tests of the sweep, and
  `test/adapters/driving/fastapi/routers/test_datalayer_read_mints_nothing.py`
  reads the next seeded ids through `new_object_id`, not `uuid.uuid4()`. It may
  share that regeneration with #5760, which moves the recording clock to its port.
  Import the docs examples before the install: their module enters
  `_example_scope()` once at import, and that install raises inside another.
