---
title: Issue #1484 already fully implemented before claim — P/X/A guards on received embargo path
type: learning
timestamp: 2026-07-21T00:00:00Z
source: ISSUE-1484
---

## Observation

Issue #1484 (Add P/X/A embargo-eligibility guards to received embargo path,
EMB-01-002, EMB-02-002) was OPEN when selected by the build skill, but
AC-1, AC-2, and AC-4 were already satisfied by commit `587a01ece`
("fix(#1484): add P/X/A embargo-eligibility guards to received-side EP/EA
path"). The `notes/embargo-lifecycle.md` file even mentioned the ACs
in-prose as implemented.

AC-3 (migrate received-side EM transitions fully to `EmbargoLifecycle`
STRICT mode) remains pending and is correctly blocked by issue #747.

## Action taken

Closed issue #1484 with a comment referencing the commit and confirming
ACs 1, 2, and 4 satisfied. AC-3 remains tracked in #747.

## Pattern to apply

When an issue's `notes/*.md` file describes the ACs as already implemented
(using past tense, referencing commit hashes or PR numbers), verify code and
tests first before claiming — then close immediately rather than implementing
again. The embargo-lifecycle.md note file is a particularly reliable indicator
since it is updated alongside implementation commits.
