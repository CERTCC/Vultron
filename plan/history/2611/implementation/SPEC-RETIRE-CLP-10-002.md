---
source: SPEC-RETIRE-CLP-10-002
timestamp: '2026-11-02T20:42:45.299075+00:00'
title: Retired requirement CLP-10-002
type: implementation
---

Retired CLP-10-002 from `specs/case-ledger-processing.yaml` (#5326).

Why: Its pre-flight identity guard (receiving_actor_id compared with case_actor_id) no longer exists and conflicts with the role gate: CLP-09-001 makes the commit gate a role check inside the one received tree (ADR-0022, CLP-10-005), and CLP-09-004 evaluates it per invocation, so a participant's delivery commits nothing.

Replacement: CLP-09-001

Final text: `plan/retired-specs/CLP-10-002.md`.
