---
status: proposed
date: 2026-11-16
created: 2026-11-16
updated: 2026-11-16
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0073, ADR-0133; specs/configuration.yaml CFG-06, CFG-07;
  specs/multi-actor-demo.yaml DEMOMA-01; notes/configuration.md; issue #4541
informed: []
stakeholder_type: [project-contributor]
---

# Each App Resolves Its Own Configuration

## Context and Problem Statement

A Vultron node reads its settings through `get_config()`, which caches one `AppConfig` for the whole process.
In Docker each container is one node, so the process-wide config is that node's config.
The in-process demo tests run several nodes as separate FastAPI apps in one process.
Each app already has its own stores and its own node root, but every app reads the same config.

So a node that reads its own config for a fact that belongs to another actor gets the right answer in process, because its config is everyone's config.
Only Docker exposes the defect.
In #1876 the CaseActor seated a report receiver with its own `default_case_roles`.
Every in-process test passed, and four Docker scenarios failed.
ADR-0133 fixed that one read, but nothing in the suite can find the next one.

How does an in-process node get a config of its own, so that the in-process suite fails where Docker fails?

## Decision Drivers

- A node's config holds only that node's own facts; a fact about another actor arrives on the wire (ADR-0133, ADR-0073).
- The in-process suite must give each node what a container gives it, as it already does for stores (DEMOMA-01-005).
- A defect of this shape must fail a test, not depend on a reviewer noticing it.
- Production nodes run one app per process, and their behavior must not change.

## Considered Options

- Each app resolves its own configuration
- Keep one config per process, and list every config read with a note on whose fact it reads
- Pass the config explicitly to every function that reads it

## Decision Outcome

Chosen option: "Each app resolves its own configuration", because it is the only option that makes the in-process suite fail on a read of another actor's fact, and it needs no change at the places that read the config.

An app may hold its own `AppConfig`.
Inside that app, `get_config()` and `load_actor_config()` return the app's config.
Work the app starts outside a request, such as background tasks, delivery and timers, also reads the app's config.
A path that cannot reach the app's config raises a wiring error; it does not fall back to the process-wide config.
An app that holds no config reads the process-wide config, as a production node does.
The in-process demo topology gives each node the config its container would have.

### Consequences

- Good, because a node that reads its own config for another actor's fact fails in the in-process suite, as it fails in Docker.
- Good, because production nodes do not change: one app per process reads the process-wide config.
- Good, because the places that read the config do not change.
- Bad, because the app's config is reached through an ambient scope, which a thread or task started without it does not inherit; each such path needs its own test.
- Neutral, because tests that set config through the process environment still work for an app that holds no config of its own.

## Validation

Tests run two apps in one process with different configs and show that each app, including its work outside a request, reads only its own.
A regression test re-creates the #1876 read and shows that the in-process suite fails on it.

## Pros and Cons of the Options

### Each app resolves its own configuration

- Good, because it gives each in-process node what its container gives it.
- Good, because a defect of the #1876 shape fails a test.
- Bad, because every path that runs outside a request must be shown to carry the app's scope.

### Keep one config per process, and list every config read with a note on whose fact it reads

- Good, because it is cheap and changes no runtime code.
- Bad, because every read on a node is that node's own setting; the defect is in using the value as a fact about another actor, which a list of reads cannot check.
- Bad, because the notes are written by hand and go stale, and no test fails when one is wrong.

### Pass the config explicitly to every function that reads it

- Good, because no ambient scope is needed.
- Bad, because it changes many call sites across core and adapters for no gain in production.
- Bad, because a later read that calls `get_config()` directly bypasses it, so the suite still cannot find the defect.

## More Information

Tracked by #4541.
The in-process harness is `vultron/demo/in_process.py`, which already gives each app its own stores (ADR-0073, DEMOMA-01-005).
