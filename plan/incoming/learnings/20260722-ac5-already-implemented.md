---
title: "AC-5 (PD-01-002/003) was already implemented before issue #1612 was worked"
type: learning
timestamp: "2026-07-22"
source: ISSUE-1612
signal: process-issue
---

Issue #1612 AC-5 asked for two new entries in `specs/project-documentation.yaml`:
PD-01-002 (notes files SHOULD NOT exceed 500 lines) and PD-01-003 (files spanning
multiple non-co-occurring Load-when scenarios SHOULD be split).

Both entries already existed in the spec before the issue was worked. The issue
body was written at planning time before the spec was updated. When working issues,
always verify spec state before assuming an AC requires a new spec entry.
