---
source: ISSUE-930
timestamp: '2026-06-16T14:08:19.522352+00:00'
title: CaseActor commit-boundary guard enforcing CLP-07 canonical entry criteria
type: implementation
---

## Issue #930 — Add CaseActor commit-boundary runtime guard enforcing CLP-07 canonical entry criteria

Implemented the commit-boundary guard (`_validate_canonical_entry()`) at `CreateLogEntryNode`
in `vultron/core/behaviors/sync/nodes/chain.py` to enforce CLP-07-001 through CLP-07-007
before entries enter the hash chain.

The guard validates:

1. Non-empty `payloadSnapshot` (unless disposition is `rejected`)
2. `payloadSnapshot` type/object pair is in the canonical allowlist
3. `payloadSnapshot.actor` is non-empty (not the CaseActor for non-case-authored entries)
4. Nested protocol objects are inlined (not bare ID strings)
5. `payloadSnapshot.context` matches the case URI

`VultronCanonicalEntryError` is raised on any violation, failing the request fast.
The allowlist (`_CANONICAL_PAYLOAD_SIGNATURES`) is a one-line extension point per AC-4.

Unit tests in `test/core/behaviors/sync/nodes/test_chain.py` cover all five rules
with passing and failing cases. CI invariant harness xfail #4 (non-empty payloadSnapshot)
is structurally addressed; remaining xfail references #789 for synthetic-event removal.

PR: <https://github.com/CERTCC/Vultron/pull/967> (merged 2026-06-15)
