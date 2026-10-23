---
source: ISSUE-1685
timestamp: '2026-07-27T16:32:09.471843+00:00'
title: 'Report: surface PEC state per participant'
type: implementation
---

## Issue #1685 — Report: surface PEC (Participant Embargo Consent) state per participant

Added `pec_state` field to `CaseTimelineEvent` in the demo report tool,
extracted from `ParticipantStatus` payload snapshots. The extractor handles
all five wire spellings: ADR-0036 dimension-object shape
(`{"consent": {"state": "SIGNATORY"}}`), plus four flat aliases
(`emConsentState`, `em_consent_state`, `embargoConsentState`,
`embargo_consent_state`). Added a dedicated PEC column between EM and CS in
both markdown and HTML renderers. Added DRPT-02-008 to specs/demo-report.yaml
and bumped spec version to 1.5.0. Added 12 new tests.

PR: <https://github.com/CERTCC/Vultron/pull/1712>
