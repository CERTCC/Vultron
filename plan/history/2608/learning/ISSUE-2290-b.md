---
title: verification field always emitted in spec-dump even when null
type: learning
timestamp: '2026-08-19T00:00:00+00:00'
source: ISSUE-2290-b
signal: design-question
---

During #2290, the user explicitly requested that `verification` be always
present in `spec-dump` output (including as `null` when not authored), rather
than omitted when absent like `rationale`, `relationships`, and `adr`.

The stated reason: "we're going to want to start enforcing non-null fields for
some of these so we should probably always include it so that it's obvious when
empty."

This means `_spec_record` in `llm_export.py` unconditionally emits
`"verification": spec.verification` while all other optional fields remain
conditional. This intentional asymmetry sets a precedent — future mandatory
fields should follow the always-emit pattern rather than the conditional one.

**Promoted**: 2026-08-24 — captured in archive only (SR-07-006 already covers it).
Docs PR: [PR URL TBD].
