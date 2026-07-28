---
source: IDEA-810
timestamp: '2026-07-21T20:25:57.383082+00:00'
title: Route two-actor demo case-actor creation to dedicated container
type: idea
---

## Outcome

Planned. Docs updated and impl issue created.

## What Was Decided

- `DemoCreateCaseActorNode` is an **ADR-0024 Actuator-shape** stub that reads
  the pre-configured case-actor URL (e.g. `VULTRON_CASE_ACTOR_ID`), writes it
  to the BT blackboard as `case_actor_id`, and delegates to the standard
  `CreateCaseActorNode` registration sequence. Lives in `vultron/demo/` (demo
  layer); core is unchanged.
- `DEMOMA-06-004` updated to require a dedicated case-actor container with its
  own isolated DataLayer (replacing the prior co-location requirement).
- `DEMOMA-06-005` added: demo must verify the case-actor container holds the
  canonical ledger after the demo completes.
- Root problem: `ResolveCaseActorUrlsNode` always derives `case_actor_id` from
  the vendor's own `server_base_url`, so it cannot route to a separate
  container. AC-3 explicitly requires bypassing this node in the demo tree.
- AC-7 added (not in original issue): two-actor seeding must register the
  case-actor container as a peer actor on both Finder and Vendor containers
  before the BT runs.
- Static case-actor URL is a **demo artifact only** — the production end-state
  is dynamic spawning (#812) where the URL is resolved at runtime.

## Docs PR

<https://github.com/CERTCC/Vultron/pull/1571>

## Implementation Issue

# 1572 — feat(demo): route two-actor demo case-actor creation to dedicated container

(blocked-by #810, child of epic #1092, size:M, 7 ACs)
