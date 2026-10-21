---
source: SPEC-RETIRE-ARCH-15-003
timestamp: '2026-10-21T17:19:35.182197+00:00'
title: Retired requirement ARCH-15-003
type: implementation
---

Retired ARCH-15-003 from `specs/architecture.yaml` (#5032).

Why: Its only raise site was the dispatcher's join-backfill gate, which one-act join backfill (CLP-07-015, #4983) left unreachable. With the gate removed, nothing extracts a case id in the dispatcher: routing is by semantics alone, and a handler that finds no case in its event refuses the activity itself (HP-05-002).

Final text: `plan/retired-specs/ARCH-15-003.md`.
