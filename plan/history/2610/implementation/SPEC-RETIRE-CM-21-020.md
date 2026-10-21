---
source: SPEC-RETIRE-CM-21-020
timestamp: '2026-10-21T19:52:24.113267+00:00'
title: Retired requirement CM-21-020
type: implementation
---

Retired CM-21-020 from `specs/case-management.yaml` (#5038).

Why: ADR-0152 ruling 3: the CASE_MANAGER commits no entry for an expired ownership-transfer Offer, so there is no offer_case_ownership_transfer_expired commit to gate or classify; CM-21-017 now states that nothing is committed

Replacement: CM-21-017

Final text: `plan/retired-specs/CM-21-020.md`.
