---
source: SPEC-RETIRE-VM-01-002
timestamp: '2026-11-03T15:51:31.498687+00:00'
title: Retired requirement VM-01-002
type: implementation
---

Retired VM-01-002 from `specs/vocabulary-model.yaml` (#5469).

Why: It names VOCABULARY as the sole type lookup, which the code no longer has: WIRE_TYPE_MAP resolves an inbound type value (VM-01-008), and VM-06-008 sets which callers may also reach the core map.

Replacement: VM-01-008

Final text: `plan/retired-specs/VM-01-002.md`.
