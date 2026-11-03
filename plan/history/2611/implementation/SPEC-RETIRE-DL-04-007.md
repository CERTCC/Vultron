---
source: SPEC-RETIRE-DL-04-007
timestamp: '2026-11-03T18:57:51.027226+00:00'
title: Retired requirement DL-04-007
type: implementation
---

Retired DL-04-007 from `specs/datalayer.yaml` (#5339).

Why: Called a received use case that depends on CaseOutboxPersistence an architectural smell. A received tree emits through that port by design in its effects stage (ADR-0111), and many received use cases do.

Final text: `plan/retired-specs/DL-04-007.md`.
