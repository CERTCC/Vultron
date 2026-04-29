---
title: DR-06 Update Per-Participant Embargo Consent State Machine
type: learning
date: 2026-04-20
source: REVIEW-26042001-supplement-DR-06
---

5-state PEC machine: NO_EMBARGO → INVITED → SIGNATORY / DECLINED / LAPSED.
Embargo meta-protocol delivery to DECLINED/LAPSED. Accept(Invite(case)) implies
embargo consent. Full case delivery requires ACCEPTED + SIGNATORY.

**Promoted**: 2026-04-28 — design in `notes/participant-embargo-consent.md`;
requirements in `specs/case-management.yaml` CM-13.
