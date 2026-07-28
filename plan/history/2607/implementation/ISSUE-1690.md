---
source: ISSUE-1690
timestamp: '2026-07-24T20:44:07.284386+00:00'
title: 'fix: fvcv-extension EM wait before finder notify-published'
type: implementation
---

## Issue #1690 — fvcv-extension: add wait_for_case_em_terminated before finder notify-published

Added `wait_for_case_em_terminated(client=finder_client)` inside a `demo_check`
block before `actor_notifies_published` for finder in `_phase_publication` of
`fvcv_extension_demo.py`. Without this guard finder could ledger a
participant-status update with `EM=ACTIVE` after the embargo was already removed
at the CaseActor, producing an out-of-causal-order entry visible in the report
as row 23 (finder updated participant status, EM=ACTIVE) appearing after row 22
(case-actor removed embargo).

Added `TestPhasePublicationEmWaitOrdering` regression test in
`test/demo/test_fvcv_extension_demo.py` verifying the EM wait precedes
finder's notify-published call using call-log tracking via `side_effect` closures.

PR: <https://github.com/CERTCC/Vultron/pull/1702>
