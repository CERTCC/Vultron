---
title: The Id Minter Draws From an Id Source — Migration Plan
status: active
kind: plan
tracks:
  - "#5676"   # epic: a re-recorded scenario equals the committed one
  - "#6114"   # slice 1: id-source port, scoped install, architecture test
  - "#6116"   # slice 2: the recording harness through the port
  - "#6117"   # slice 3: the docs-example generator through the port
description: >
  The unbuilt migration to ADR-0185: the one object id minter draws from an
  id-source port, and a run that needs repeatable ids replaces the source for a
  block instead of patching uuid.uuid4 for the whole process.
related_specs:
  - specs/object-ids.yaml
  - specs/architecture.yaml
  - specs/demo-ci.yaml
---

# The Id Minter Draws From an Id Source — Migration Plan

ADR-0185 decides that the one minter, `new_object_id` (OID-01-004), draws from an
id-source port, and that a run needing repeatable ids installs its source for a
block. The code does not do this yet: the minter calls `uuid.uuid4`, and two runs
patch it process-wide. This note holds the order of the work and the rules each
slice keeps.

## Rules every slice keeps

- **Nothing patches the standard library's draw.** A reproducible run supplies
  its ids only through the scoped install, because a patch of `uuid.uuid4` also
  reaches py_trees and moves a recording's ids with the tree's shape.
- **Mint anywhere, but only through the minter.** Ids are not threaded to the
  act's edge: an id is a name with no value two reads must agree on, and the
  `id_` default factories run outside any tree run (ADR-0185, option 3).
- **The application factory installs nothing.** The system source is the
  default, because `create_app()` must not change process-wide state
  (ARCH-16-001).
- **The install lives beside the minter.** It sits in `vultron/core/models/`, so
  the docs-example generator in the wire layer can reach it (ARCH-22-001).
- **An install restores, and does not nest.** The previous source comes back on
  exit and on an exception; a second install inside an active one fails, because
  the two runs would silently share one stream of ids.
- **Exemptions shrink, never grow.** Each slice removes its own entry from
  `NON_ID_RANDOM_UUID_EXEMPTIONS` in the same PR (ARCH-18-002); the database-name
  entry stays, because that draw names no object.

## Slices, in order

1. **Foundation** (#6114). The id-source port and system source, the minter
   drawing from the installed source, the scoped install, the architecture test's
   minter site moved to the system source, and the OID-01 rule that cites
   ADR-0185.
2. **Recordings** (#6116). `deterministic_run()` installs `SeededUuid4` through
   the port and drops its `sys.modules` sweep; every recording is regenerated
   once. It may share that regeneration with #5760, which moves the recording
   clock to its port.
3. **Docs examples** (#6117). `_example_scope()` installs `_ScopedIds` through
   the port; the example corpus does not change.

Slices 2 and 3 are independent once slice 1 lands.
