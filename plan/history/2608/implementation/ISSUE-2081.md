---
source: ISSUE-2081
timestamp: '2026-08-07T20:10:05.806120+00:00'
title: validate VFD/RM/PXA transitions in CreateParticipantStatusNode
type: implementation
---

## Issue #2081 — fix(status-write): validate VFD/RM/PXA transitions in CreateParticipantStatusNode

Implements fail-closed transition validation in `CreateParticipantStatusNode.update()`. VFD, RM, and PXA state jumps are now validated before any DataLayer write; illegal transitions return `Status.FAILURE`. Closes #2081 and #1903.

PR: <https://github.com/CERTCC/Vultron/pull/2095>
