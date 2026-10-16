---
source: SPEC-RETIRE-VAM-07-001
timestamp: '2026-10-16T19:00:09.081726+00:00'
title: Retired requirement VAM-07-001
type: implementation
---

Retired VAM-07-001 from `specs/vultron-as2-mapping.yaml` (#4707).

Why: ADR-0137 makes Add(Note) the one message that attaches a note; a received Create(Note) is not a protocol message (VAM-01-011) and this codebase refuses it as an unrecognized activity (VAM-01-010).

Replacement: VAM-01-011

Final text: `plan/retired-specs/VAM-07-001.md`.
