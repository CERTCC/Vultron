---
title: spec priority enum uses MUST_NOT with underscore, not MUST NOT with space
type: learning
timestamp: 2026-08-20T18:30:00Z
source: ISSUE-2393
signal: spec-ambiguity
---

The `priority:` field in `specs/*.yaml` files uses `MUST_NOT` and `SHOULD_NOT`
(underscores), NOT `MUST NOT` / `SHOULD NOT` (spaces). The pydantic enum that
spec-lint validates against uses underscores.

MS-02-002 reads "Valid priority values: `MUST`, `MUST NOT`, `SHOULD`, `SHOULD_NOT`,
`MAY`" — this prose uses spaces, but the actual validator enum uses underscores.
Changing `MUST_NOT` → `MUST NOT` with sed breaks spec-lint with a FATAL registry
load error.

**When writing new spec entries: always use `MUST_NOT` and `SHOULD_NOT` with
underscores for the `priority:` field.**
