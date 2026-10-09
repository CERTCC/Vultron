---
source: CONCERN-4391
timestamp: '2026-10-09T17:06:58.557838+00:00'
title: ADR-0003 narrowed to the legacy simulator, not superseded
type: learning
---

## Problem

ADR-0003 "Build our own Behavior Tree engine in Python" (2023-10-23) is still
`status: accepted`, with the chosen option "Build our own". The project
subsequently adopted `py_trees`:

- ADR-0008 "Use py_trees for Handler BT Integration" (2026-02-19, `accepted`)
- ADR-0044 "py_trees Typed Ports Adoption" (`accepted`), which generated
  BTND-03-009 through BTND-03-011 as MUST-level requirements about `py_trees`
  port declarations
- `pyproject.toml:51` declares `py-trees>=2.6.0` as a runtime dependency

ADR-0003 carries no `superseded_by` link and is not archived, so it sits in the
live set as an accepted decision that the project reversed.

This is a different defect from stale implementation detail in an otherwise-sound
record (concern #4389). Here the *chosen option* no longer holds. An agent that
reads ADR-0003 as settled fact — and `status: accepted` is the signal telling it
to, per ADR-0043 — learns that the project builds its own behavior-tree engine.

A second signal that it was never revisited: a corpus scan found ADR-0003 among
the ADRs with no `Generated spec requirements:` line, zero citations from
`specs/*.yaml`, and zero citations from `notes/*.md`, with a topical keyword
search finding its decision nowhere else.

## What this needs

A human verdict on the disposition, which is `decision-audit`'s job rather than
something to fix mechanically. The plausible outcomes:

- `superseded by` ADR-0008 (and/or ADR-0044), with the reciprocal `supersedes`
  field set — MS-14-011 requires supersession links to be bidirectional, and the
  loader fails a one-sided pair.
- Moved to `docs/adr/archived/` per MS-14-004, so it stays out of the default
  `docs/adr/` context sweep.
- Something narrower, if part of the original decision does still hold — the
  custom engine predates `py_trees` adoption by over two years and some of the
  reasoning may survive in how the project wraps it.

Worth checking during the audit whether other early ADRs (0002, 0004, 0007) have
the same problem, since they are the same vintage and concern the same subsystem.

## Related

- Concern #4389 — ADRs carry stale implementation detail (this was routed out of it)
- Epic #4194 — spec and ADR governance
- ADR-0043 — ADR status as confidence signal (why `accepted` is load-bearing here)
- ADR-0120 — ADR lifecycle epochs and edit tiers

Where: docs/adr/0003-build-our-own-behavior-tree-engine-in-python.md

**Resolved**: 2026-10-09 — resolved fully in the docs PR; no implementation issues.
The premise was half right: `vultron/bt/` (legacy simulator, vultrabot demos, `test/bt/`) still runs on the custom engine, and ADR-0008 already scoped `py_trees` to handler execution.
ADR-0003 was marked `partially_superseded_by` ADR-0008 with a dated amendment narrowing it to the simulator; ADR-0008 got the reciprocal `partially_supersedes`; ADR-0004 got an amendment scoping it to `vultron.bt.base`.
ADR-0002 and ADR-0007 were checked and still hold.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4421>.
