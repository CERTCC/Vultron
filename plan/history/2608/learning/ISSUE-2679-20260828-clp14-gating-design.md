---
title: CLP-14 timestamp checks gated on case_published to preserve backward compat
type: learning
timestamp: "2026-08-28T00:00:00Z"
source: ISSUE-2679
signal: design-question
---

All CLP-14 timestamp invariant checks in `_validate_canonical_entry` are
gated on `case_published is not None`. When the caller omits `case_published`
(the default), no timestamp checks run — the function behaves as before.

Decision rationale: the issue required AC-4 ("all existing tests pass"). Real
AS2 activity payloads serialized via `model_dump` include `published` from
`VultronObject._now_utc()`. But test fixtures that directly construct
`payload_snapshot` dicts (bypassing the wire layer) do not include
`published`. Making the checks unconditional would fail those fixtures.

Consequence: CLP-14 enforcement is opt-in at the call site. The production
call site (`chain.py`) does NOT currently pass `case_published`, meaning
enforcement only fires via conformance tests post-hoc. See the companion
`concern` learning for the follow-up issue.

## Audit disposition (2026-09-02)

Closed decision, no promotion owed (BW-07-008). The decision was made, applied, and shipped in its originating PR; the commit and PR body are its record. Archived without promotion.
