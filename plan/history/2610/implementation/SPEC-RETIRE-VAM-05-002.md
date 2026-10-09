---
source: SPEC-RETIRE-VAM-05-002
timestamp: '2026-10-08T16:16:24.176350+00:00'
title: Retired requirement VAM-05-002
type: implementation
---

Retired VAM-05-002 from `specs/vultron-as2-mapping.yaml` (#4292).

Why: ADR-0122 rev 2 retires the direct activation of an embargo by Add(EmbargoEvent, target=Case): adding an embargo to the case is what proposing does, and the case owner activates a proposal with Accept(EmbargoEvent, target=Case).

Replacement: VAM-05-008

Final text: `plan/retired-specs/VAM-05-002.md`.
