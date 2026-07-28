---
source: ISSUE-1519
timestamp: '2026-07-20T19:01:05.814640+00:00'
title: Migrate embargo Invite/proposal semantic activity reads off dl.read
type: implementation
---

## Issue #1519 — Migrate embargo Invite/proposal semantic activity reads off dl.read (core state)

Eliminated all 3 DL-06 Category-B wire re-reads of stored `Invite` AS2 Activities from core code. Replaced with `pending_embargo_proposal_index: dict[str, str]` (embargo_id → proposal_id) on `VulnerabilityCase`.

Sites closed:

1. `dispatcher._extract_case_id` — removed `dl.read(invite_id)` special case; added `case_id`/`embargo_id` properties to `RejectInviteToEmbargoOnCaseReceivedEvent`
2. `_resolve_case_for_embargo_acceptance` — removed `dl.read(invite_id)` fallback
3. `RejectInviteToEmbargoOnCaseReceivedUseCase.execute()` — used `request.case_id`/`request.embargo_id` from event properties
4. `find_embargo_proposal` / `dl.list_objects("Invite")` — replaced with `find_embargo_proposal_id(case)` reading core state index

Index populated from receive-side (`InviteToEmbargoOnCaseReceivedUseCase`) and trigger-side (`SvcProposeEmbargoUseCase._handle_result`).

Architecture ratchet tightened: `"Invite"` removed from `ACTIVITY_TYPE_EXEMPTIONS` (DL-05-004).

10 new AC-5 tests in `test/core/use_cases/received/test_embargo_proposal_index.py`. All 5127 tests pass.

PR: <https://github.com/CERTCC/Vultron/pull/1541>
