---
source: ISSUE-1977
timestamp: '2026-08-05T23:29:07.060837+00:00'
title: Extract participant-status convergence predicate to core
type: implementation
---

## Issue #1977 — Extract participant-status convergence predicates to vultron/core/predicates/participants.py

Extracted `_all_fetchable_participants_rm_closed` convergence logic from `vultron/demo/helpers/verification.py` into a new pure-function module `vultron/core/predicates/participants.py`.

The new `all_participants_rm_closed(participants: list[CaseParticipant]) -> bool` function has no DataLayerClient dependency, enabling direct unit testing with in-memory objects. The demo wrapper now fetches participants, converts via `.to_core()`, and delegates to the pure predicate.

15 new tests added covering all RM states, CASE_MANAGER exclusion, CaseActorParticipant exclusion, and no-status-record case. Architecture ratchets (core-no-wire, core-no-adapter) remain clean.

PR: <https://github.com/CERTCC/Vultron/pull/2023>
