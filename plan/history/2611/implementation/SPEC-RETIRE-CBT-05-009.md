---
source: SPEC-RETIRE-CBT-05-009
timestamp: '2026-11-02T16:33:09.045620+00:00'
title: Retired requirement CBT-05-009
type: implementation
---

Retired CBT-05-009 from `specs/case-bootstrap-trust.yaml` (#5470).

Why: CBT-01-007 now requires each bootstrap participant inline (ADR-0170), so a participant named only by URI is absent under CBT-05-008 for every implementation, and this codebase's rule that treats it as absent says nothing CBT-05-008 does not.

Replacement: CBT-05-008

Final text: `plan/retired-specs/CBT-05-009.md`.
