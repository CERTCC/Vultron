---
title: SR-11 backfill — 698 protocol MUST specs carry lint_suppress pending story mapping
type: learning
timestamp: 2026-08-25T17:55:00Z
source: ISSUE-2585
signal: concern
---

AC-7 required zero `spec-lint` hard errors after the SR-11 backfill.
The traceability document only covered 150 of the ~848 protocol MUST specs.
The remaining 698 were given `lint_suppress: [missing_story_reference]` so CI
stays green while story coverage is completed incrementally.

These suppressed specs are visible in any spec YAML file under `specs/` as
entries with `lint_suppress:\n- missing_story_reference` but no `stories:` field.

**Follow-on work needed:** open a tracking issue or epic to drive story coverage
for the 698 suppressed specs. As each spec gains a `stories:` entry, remove its
suppression. The hard-error gate then enforces completeness automatically for
any newly-authored protocol MUST spec.
