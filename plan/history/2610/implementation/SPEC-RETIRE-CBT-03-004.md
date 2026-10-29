---
source: SPEC-RETIRE-CBT-03-004
timestamp: '2026-10-29T13:49:31.723860+00:00'
title: Retired requirement CBT-03-004
type: implementation
---

Retired CBT-03-004 from `specs/case-bootstrap-trust.yaml` (#5334).

Why: The receiver's bootstrap replay Question had no handler and asked for Create(VulnerabilityCase), which no longer delivers a case copy (PCR-02-005); ADR-0163 gives recovery of a dropped Invite to the CASE_MANAGER, prompted by the participant's post-seed position statement (SYNC-17-008).

Replacement: SYNC-17-008

Final text: `plan/retired-specs/CBT-03-004.md`.
