---
source: ISSUE-2097
timestamp: '2026-08-07T20:40:40.750469+00:00'
title: 'fix: resolve wire-layer pydantic typing TODOs in case_participant.py, collections.py,
  object_types.py'
type: implementation
---

## Issue #2097 — fix: resolve wire-layer pydantic typing TODOs

Removed stale TODOs from `case_participant.py` with inline rationale. Replaced
`collections.py` duplicate-ignoring TODO with `# see #2110` (follow-on issue
filed). Clarified `as_Relationship.relationship` field type comment in
`object_types.py` (AS2 spec allows string term or URI; `str` covers both).

PR: <https://github.com/CERTCC/Vultron/pull/2111>
