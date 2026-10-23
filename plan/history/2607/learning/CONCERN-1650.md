---
source: CONCERN-1650
timestamp: '2026-07-24T15:12:06.825058+00:00'
title: CI linter + metaspec enforcing ECA format for DEMOMA scenario groups
type: learning
---

DEMOMA scenario workflow specs were written as prose ordered-MUST
statements rather than the ECA format (trigger/preconditions/steps/postconditions)
used by the rest of the spec corpus. PR #1605 retrofitted existing groups, but
there was no enforcement preventing regression on new groups. The Vendor-role
precondition gap (DEMOMA-12, CONCERN-1634) was partly enabled by prose
postconditions that carried no typed caller obligations.

**Resolved**: 2026-07-24 — implementation tracked in #1665.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1664>.
Spec: `specs/meta-specifications.yaml` (MS-13-004).
Notes: `specs/multi-actor-demo.yaml` (DEMOMA-14 ECA fix).
