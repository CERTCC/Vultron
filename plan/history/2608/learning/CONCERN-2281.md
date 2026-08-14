---
source: CONCERN-2281
timestamp: '2026-08-14T18:29:07.309709+00:00'
title: Pre-harness demo CI empty artifact
type: learning
---

## Context

Issue #2239 (PR #2279) moved the case-ledger dump into a shared `scenario_harness()`
so that any phase failure inside a scenario body still dumps the ledgers, then
asserts. That closes the in-scenario case, which was the reported bug.

It does **not** close the case where the scenario never reaches the harness at
all.

## Problem

If a demo dies *before* `scenario_harness()` is entered, nothing writes a
manifest and `devlogs/` stays empty:

- the health-check gate in each `main()` calls `sys.exit(1)`,
- an import error in the scenario module,
- a `docker compose` startup failure that never gets as far as the runner.

Downstream, the failure looks exactly like ISSUE-2239 did:

1. `mkdir -p devlogs` creates an empty directory with no files.
2. `upload-artifact` runs with the default `if-no-files-found: warn` and
   publishes nothing.
3. The `invariant-harness` job's download step dies on the missing artifact
   and reports nothing about the protocol.

This is the residual hole in DEMOCI-10-002's guarantee that "the artifact
upload then always has something to upload".

## Resolution

**Resolved**: 2026-08-14 — implementation tracked in #2312.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2311>.
Spec: `specs/demo-ci.yaml` (DEMOCI-10-006).
Notes: `notes/demo-ci-invariants.md` (Layer 2 — Pre-harness failures).
