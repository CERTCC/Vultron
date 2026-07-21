---
source: ISSUE-1521
timestamp: '2026-07-21T16:18:01.395755+00:00'
title: Audit Category-C envelope reconstitution; confirm seam correct; add reconstitution
  tests
type: implementation
---

## Issue #1521 — Envelope reconstitution: verify need, then provide a wire/adapter-owned opaque seam

Audited all live reply-construction paths against DL-06-004 (ADR-0035 Category C). Four adapter methods (`accept_case_invite`, `accept_case_participant_offer`, `accept_embargo`, `reject_embargo`) read stored wire activities for verbatim envelope reconstitution. All four are already in the adapter layer (`vultron/adapters/driven/trigger_activity_adapter/`); no new seam was needed. Added 4 tests verifying inline `object_` and `in_reply_to` preservation. Notes updated with full audit findings.

PR: <https://github.com/CERTCC/Vultron/pull/1559>
