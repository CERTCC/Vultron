---
source: ISSUE-931
timestamp: '2026-06-15T17:30:04.358574+00:00'
title: ParticipantStatus emConsentState and cvdRole snapshots
type: implementation
---

## Issue #931 — Add emConsentState and cvdRole fields to ParticipantStatus schema and populate at write sites

Implemented ParticipantStatus schema updates for both core and wire models, populated emConsentState and cvdRole across participant-status write paths, and promoted case-ledger invariant #9 from xfail to passing coverage (with value validation).

PR: <https://github.com/CERTCC/Vultron/pull/960>
