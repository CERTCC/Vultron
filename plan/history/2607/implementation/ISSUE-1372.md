---
source: ISSUE-1372
timestamp: '2026-07-14T16:39:04.211022+00:00'
title: fix CaseActor roster entry and correct suggest-actor vocab to= fields
type: implementation
---

## Issue #1372 — fix: add CaseActor roster entry and correct to= fields in suggest-actor vocab examples

Added `_CASE_ACTOR` (as_Service) to the vocab examples roster in `_base.py`, corrected `actor=` and `to=` fields in `offer_case_participant()`, `accept_case_participant_offer()`, and `reject_case_participant_offer()` to reflect ADR-0026 actor boundaries. Added 4 new unit tests. PR: <https://github.com/CERTCC/Vultron/pull/1411>
