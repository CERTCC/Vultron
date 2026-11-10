---
title: The Id Minter Draws From an Id Source
status: active
kind: guidance
description: >
  How a run that needs repeatable object ids gets them under ADR-0185: the one
  minter draws from an id-source port, and the run installs its source for a
  block instead of patching uuid.uuid4.
related_specs:
  - specs/object-ids.yaml
  - specs/architecture.yaml
  - specs/demo-ci.yaml
---

# The Id Minter Draws From an Id Source

ADR-0185 decides that the one minter, `new_object_id` (OID-01-004), draws from an
id-source port, and that a run needing repeatable ids installs its source for a
block (OID-01-011, OID-01-012). A scenario recording (`deterministic_run()`) and
the docs-example generator (`_example_scope()`) both install their sources this
way, and nothing patches `uuid.uuid4`.

A run installs its source with `install_id_source(source)`, a context manager in
`vultron.core.models._helpers`. The source is any callable that returns a
`uuid.UUID` (the `IdSource` Protocol), so `SeededUuid4` and `_ScopedIds` fit as
they are. A nested install raises `VultronIdSourceInstalledError`.

## Rules

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
- **No example scope opens inside a recording.** The docs examples enter
  `_example_scope()` once at first import, so `vultron.demo.determinism` imports
  them with itself, before any `deterministic_run()` install; a first import
  inside the install would raise (`test_determinism.py`,
  `TestDocsExamplesLoadBeforeTheInstall`).
- **Exemptions do not grow.** `NON_ID_RANDOM_UUID_EXEMPTIONS` holds only the
  database-name entry, because that draw names no object; the exact-set assert in
  `test_no_function_but_the_system_id_source_draws_a_random_uuid` fails on a new
  draw or replacement (OID-01-004, OID-01-012).
- **A test that observes the minter reads it through the port.** A test that
  replaces or calls `uuid.uuid4` to watch the minter checks nothing, because the
  minter draws from the id source; read the next ids with `new_object_id`.
