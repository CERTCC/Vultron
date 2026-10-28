---
source: CONCERN-5319
timestamp: '2026-10-28T16:16:09.804532+00:00'
title: In process, hosted_actor_ids() lists every node's actors, so each node opens
  empty stores for foreign actors
type: learning
---

## Summary

When several in-process nodes share one process (the demo tests' isolated apps, and the scenario recorder `uv run export-demo-recordings`), `actor_hosts.hosted_actor_ids()` lists the actors of **every** node, not only the node that asks. In memory mode it returns `get_all_actor_datalayers()`, the process-wide store cache, which ignores the `db_url` each node uses. A node that iterates its hosted actors, such as `GET /actors/` (`get_actors`), then opens an empty store for each foreign actor under its own deployment.

## Evidence

One full recording run of the 11 scenarios (#3901) logs about 1,200 WARNINGs of two kinds:

- `Actor 'http://vendor:7999/api/v2/actors/primary' has cached DataLayers under more than one db_url` (`datalayer_sqlite/__init__.py`, `get_all_actor_datalayers`)
- `Store sqlite:///file:node-http_vendor_7999-primary?... is shared by two distinct actor ids` (`datalayer_sqlite/engine.py`)

`create_isolated_actor_app` also opens a placeholder `.../actors/primary` store on every node, which adds to the count.

## Why it matters

The recordings are still correct: `get_actors` reads each actor's record from the store, and a foreign actor's store on this node is empty, so it is not listed. But the noise hides any real warning in a recording run (the recorder defaults to `--log-level ERROR` for that reason), and any future caller of `hosted_actor_ids()` that acts on the list, rather than reading records from it, would act on actors this node does not host. Docker never shows this, because each container has its own process.

## Possible directions

- Let `hosted_actor_ids()` take the node's `db_url` and, in memory mode, return only the actors cached under that URL; pass it from `get_actors`.
- Stop `create_isolated_actor_app` opening a store for an actor that is never created there.

Where: vultron/adapters/driven/actor_hosts.py

**Resolved**: 2026-10-28 — implementation tracked in #5338.

Docs PR: <https://github.com/CERTCC/Vultron/pull/5337>.

Spec: `specs/datalayer.yaml` (DL-07-011).
