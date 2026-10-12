---
source: CONCERN-4469
timestamp: '2026-10-12T15:50:01.203412+00:00'
title: Code comments still cite ADR-0099 detail numbers that ARCH-25 replaced
type: learning
---

## Problem

PR #4466 (#4409) turned ADR-0099's ten numbered decision details into requirements ARCH-25-001 to ARCH-25-010. It converted every "detail N" citation in `specs/`, `notes/` and the AGENTS.md files, and added MS-11-007 with a test scanning `specs/` and `notes/`.

About 200 mentions of "ADR-0099 detail N" remain in Python docstrings and comments under `vultron/` and `test/`. They still send a reader into the ADR body to learn the rule, which ADR-0127 says routine context should not need. The MS-11-007 test does not scan code, so nothing stops new ones.

## Open questions

- Should code comments cite the ARCH-25 requirement IDs instead, converted in one mechanical pass?
- Should the MS-11-007 scan extend to `vultron/` and `test/`, or should code comments stay out of scope as history?

## Reference

Found by the #4409 builder; out of that issue's scope (it covered `specs/` and `notes/` only).

Where: vultron/, test/ (docstrings and comments citing ADR-0099 detail N)

**Resolved**: 2026-10-12 — implementation tracked in #4503 (code conversion and scan extension), after #4502 (widened detector on git grep). Decided in planning: code comments and docstrings fall under MS-11-007; enforcement runs as one git grep call in the test (measured ~0.06 s vs ~1 s for a Python read-every-file scan). Both tasks are blocked by #4409 (PR #4466).

Docs PR: <https://github.com/CERTCC/Vultron/pull/4504>.
