---
source: SPEC-RETIRE-CLP-07-008
timestamp: '2026-10-21T00:22:06.683949+00:00'
title: Retired requirement CLP-07-008
type: implementation
---

Retired CLP-07-008 from `specs/case-ledger-processing.yaml` (#3742).

Why: ADR-0107 records a received activity's body verbatim, so the CASE_MANAGER no longer resolves a nested reference from its store to inline it into a payloadSnapshot; CLP-07-006 forbids that resolution, which leaves no canonicalization path for this check to guard.

Replacement: CLP-07-006

Final text: `plan/retired-specs/CLP-07-008.md`.
