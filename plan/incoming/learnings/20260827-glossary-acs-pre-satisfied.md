---
title: "Issue #2523 listed three glossary terms as missing that were already present"
type: learning
timestamp: "2026-08-27T19:45:15Z"
source: ISSUE-2523
signal: process-issue
---

Issue #2523 ([Docs] Glossary: align reference/glossary.md) listed these
"new terms to add at minimum":

- Observer role (ADR-0057)
- Lifecycle-staged types (ADR-0033: IncomingReport / Case / EmbargoedCase)
- Wire/core distinction (ADR-0017: Two-Branch Hierarchy)

All three were already present and accurate in the glossary when work began.
The only genuine gap was `CVDRole.FINDER` deprecated per ADR-0078 (accepted
2026-08-26, one day before this issue was executed).

**Why:** The issue body was written before ADR-0057/0033/0017 were reflected
in the glossary, then the glossary was updated by another PR but the issue
description was not refreshed.

**How to apply:** For docs audit issues, verify the "missing terms" list
against the current file before estimating scope. The pre-claim AC
verification gate in `build` only fires on `- [ ] AC-N:` format items;
prose-format AC lists (as in this issue) skip the gate entirely. A quick
grep of the target file for each listed term costs less than writing a
study plan based on stale ACs.
