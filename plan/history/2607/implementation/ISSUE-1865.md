---
source: ISSUE-1865
timestamp: '2026-07-31T18:41:56.330560+00:00'
title: 'fix(pec): allow ACCEPT/DECLINE directly from NO_EMBARGO'
type: implementation
---

## Issue #1865 — fix(pec): allow ACCEPT/DECLINE directly from NO_EMBARGO (ADR-0048)

Added `ACCEPT: NO_EMBARGO → SIGNATORY` and `DECLINE: NO_EMBARGO → DECLINED`
to the PEC FSM. Fixed `_SignEmbargoConsentLeafNode` which hardcoded `PEC.NO_EMBARGO`
instead of using `participant.embargo_consent_state`, causing a silent CM-10-001
violation. Added regression tests covering all starting states (NO_EMBARGO,
INVITED, LAPSED, SIGNATORY).

PR: <https://github.com/CERTCC/Vultron/pull/1882>
