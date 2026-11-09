---
status: proposed
date: 2026-11-09
created: 2026-11-09
updated: 2026-11-09
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; issues #5676, #5761, #5584, #5760, #6114, #6116, #6117;
  ADR-0010, ADR-0176; specs/object-ids.yaml OID-01-004;
  specs/architecture.yaml ARCH-16-001, ARCH-22-001;
  specs/demo-ci.yaml DEMOCI-11-018, DEMOCI-11-025, DEMOCI-11-054
informed: []
stakeholder_type: [project-contributor]
---

# The One Id Minter Draws From an Id Source, Not a Patched uuid4

## Context and Problem Statement

Every new object id comes from one minter, `new_object_id` (OID-01-004), and `test/architecture/test_single_object_id_minter.py` fails on a random UUID drawn anywhere else in `vultron/`.
The minter calls `uuid.uuid4` directly, so a run that needs repeatable ids replaces that function for the whole process.
Two runs do this today: a scenario recording (`deterministic_run`, seeded per DEMOCI-11-025) and the docs-example generator (`_example_scope`).

The replacement reaches every caller of `uuid.uuid4`, not only the minter.
py_trees draws one for every `Behaviour` it builds and for every blackboard client.
Inside a recording those draws take seeded ids, so the ids a recording holds depend on how many tree nodes the run built.
Adding one node to a tree moves every later object id in every recording, and CI records every scenario at the base and the head of a demo pull request (DEMOCI-11-054), so the churn shows on pull requests that change no protocol behaviour.
The seeded draws also collide with ids the py_trees client registry already holds, which is why the recording harness must clear the blackboard between runs.

ADR-0176 decided how time enters the application and left ids to this decision.
How does a generated id enter the application, and where may it be minted?

## Decision Drivers

- A recording's ids must depend only on the objects the application mints, not on what libraries draw.
- A run that needs repeatable ids must supply them through one declared place, not by replacing a standard-library function.
- Every new object id still comes from one minter shared by the core and wire layers (OID-01-004).
- The application factory must not change process-wide state (ARCH-16-001).
- The wire layer may import only `vultron.core.models` and `vultron.core.states` (ARCH-22-001), and the docs-example generator is in the wire layer.
- The rule must be enforced by a test, not by audits.
- The change must not make every model construction and every test take an id.

## Considered Options

1. **Keep patching `uuid.uuid4`.** The one minter already confines every draw; the runs that need repeatable ids keep replacing the function.
2. **Every id is an argument.** No core model has an `id_` default; every construction site passes an id drawn from an injected id source, as ADR-0176 does for time.
3. **Ids minted at the act's edge.** An act places an id source in the tree run's shared state beside its instant, and code in the act mints from it.
4. **Derive every id from content.** Every id is a `uuid5` of what the object holds, so the same content always gets the same id.
5. **The one minter draws from an id source.** The minter calls an id-source port; the system source is installed by default, and a run that needs repeatable ids replaces it for a block through one scoped install.

## Decision Outcome

Chosen option: "The one minter draws from an id source", because it is the only option that stops library draws from consuming a recording's ids without making every model construction take an id.
Option 1 leaves the defect in place: the patch reaches py_trees, so a recording's ids depend on the tree's shape.
Option 2 meets every driver but one: it changes every model construction in `vultron/` and every test that builds a model, and no driver needs it.
Time needed that cost because one act must decide and record against one instant (ADR-0176); an id is a name, so two ids of one act have no value to agree on.
Option 3 cannot reach the places that mint most ids: the `id_` default factories of `CoreRecord` and `as_Base` run outside any tree run, in parsing, adapters and tests, so it would need option 2 as well.
Option 4 gives two distinct objects with the same content the same id, which breaks OID-01-002; content-derived ids stay what they are today, the way an answer names itself (`derived_object_id`), not the way a new object is named.

The decision has five parts.

- **Ids are minted anywhere, through the one minter.** Any code may mint a new object id, but only by calling the one minter, directly or through an `id_` default factory.
  No code under `vultron/` draws a random UUID for an object id any other way, and no code replaces the standard library's draw.
- **The minter draws from an id source.** The id source is a port with one operation, which returns a fresh version-4 UUID.
  The system id source implements it with `uuid.uuid4`, and is the one function in `vultron/` that draws a random UUID for an object id.
- **The system source is the default, and the application factory installs nothing.** The system source is the correct source for every run except a run that must repeat byte for byte.
  The application factory does not install an id source, because it must not change process-wide state (ARCH-16-001).
- **A reproducible run replaces the source for a block.** A run that needs repeatable ids installs its source through one scoped install that lives beside the minter, so the wire layer can reach it.
  The install restores the previous source when the block ends, also when the block raises.
  An install while another install is active fails, because two reproducible runs in one block would take each other's ids without anyone seeing it.
  The installed source is process-wide, as the patch is today: in-process recordings run several nodes in one process, and they draw from one seeded stream.
- **Derived ids and non-id draws are unchanged.** An id derived from what an activity answers (`derived_object_id`, ID-04-004) is not minted and does not touch the id source.
  A random UUID drawn for something that is not an object id, such as the name of an in-memory database, stays a listed exemption.

### Consequences

- Good: a recording's ids depend only on the objects the scenario mints, so a refactor of tree shape no longer changes a recording.
- Good: py_trees draws real ids again, so seeded draws no longer collide in its client registry.
- Good: the recording harness drops its sweep of every loaded module, and the docs-example generator drops its patch of the `uuid` module.
- Good: the change is confined to the minter, the two reproducible runs and the architecture test; no model, node or test fixture changes.
- Neutral: the id source is process-wide state; a thread that mints while a reproducible run's install is active takes one of its ids.
  This is true of today's patch, and both reproducible runs are single-threaded or draw in a fixed order.
- Neutral: an object built and discarded still takes an id from the source, so a code change that mints more objects moves the later ids of a recording.
  That is a change in what the application mints, and the recording is meant to show it.
- Bad: every committed recording changes once, when py_trees stops taking seeded ids.

## Validation

- The architecture test in `test/architecture/test_single_object_id_minter.py` will name the system id source as the one site that draws a random UUID for an object id, and will fail on a replacement of the `uuid` module's draw anywhere in `vultron/`; the exemptions for the two reproducible runs will be removed.
- A test will show that the minter and both `id_` default factories draw from an installed source.
- A test will show that a scoped install restores the previous source, also on an exception, and that a nested install fails.
- A test will show that building py_trees behaviours inside a recording run draws nothing from the seeded source.
- A recording regenerated twice on one commit will give the same bytes.

## More Information

The work is tracked under #5676, in three slices: the id-source port, the scoped install and the architecture test first (#6114); then the recording harness through the port, with every recording regenerated once (#6116); and the docs-example generator through the port (#6117).
The plan and the rules the slices keep are in `notes/id-source.md`.

OID-01-004 stays as stated; #6114 adds the id-source rule to the OID-01 group with the architecture test as its verification.
