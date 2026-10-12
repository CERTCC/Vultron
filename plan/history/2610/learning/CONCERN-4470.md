---
source: CONCERN-4470
timestamp: '2026-10-12T15:50:01.583402+00:00'
title: MS-11-007 catches only detail N; other numbered-part citations still dereference
  record bodies
type: learning
---

## Problem

MS-11-007 (added in PR #4466, #4409) forbids a spec or note from citing a numbered *detail* of a decision record, and its test matches only the "detail N" shape.

Specs and notes still cite numbered parts of other records in other shapes, for example "ADR-0009 Rule 1" and "ADR-0107 step 5". These resolve their meaning by pointing into a record body, which ADR-0127 forbids just as much, but the check does not see them.

## Open questions

- Should MS-11-007 and its test cover any numbered part of a record (rule, step, detail, point, …)?
- Each such citation needs the rule it names written down as a requirement or note first, as #4409 did for ADR-0099. How large is that set, and does any record need a reflow like ADR-0099's?

## Reference

Found by the #4409 builder; out of that issue's scope.

Where: specs/, notes/; test/metadata/test_no_adr_detail_citations.py

**Resolved**: 2026-10-12 — implementation tracked in #4502, with #4503 extending the same check to code. Decided in planning: MS-11-007 covers any numbered part of a record (detail, rule, step, option, part), anchored to a nearby record ID except for "detail"; 14 citations in specs/notes to convert, no record needs an ADR-0099-style reflow; the "ADR-0015 Option 4" citations point at an archived record (docs/adr/archived/0015-create-case-at-report-receipt.md) that ADR-0041 superseded. Blocked by #4409 (PR #4466).

Docs PR: <https://github.com/CERTCC/Vultron/pull/4504>.
