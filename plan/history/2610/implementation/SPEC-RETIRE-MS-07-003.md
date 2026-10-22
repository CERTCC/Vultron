---
source: SPEC-RETIRE-MS-07-003
timestamp: '2026-10-22T17:42:19.694476+00:00'
title: Retired requirement MS-07-003
type: implementation
---

Retired MS-07-003 from `specs/meta-specifications.yaml` (#4481).

Why: It asked authors to record every cross-reference at both ends with the inverse type. Those second copies drifted to opposite verbs and closed loops in the requirements graph; a link is now recorded once, and the reverse direction is computed from the requirements graph (`relation_graph.upstream_graph()`).

Replacement: SR-13-012

Final text: `plan/retired-specs/MS-07-003.md`.
