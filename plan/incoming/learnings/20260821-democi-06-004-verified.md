---
title: DEMOCI-06-004 scenario filter verified — 4 on PR, 9 on push
type: learning
timestamp: 2026-08-21
source: ISSUE-2460
signal: verification
---

Verified that the `scenarios` pre-filter job (DEMOCI-06-004, PR #2118) is
working correctly.

**PR run** (run ID 32416027725, PR #2448):

- fv, fvcv-handoff, fcvcv, fcv-reject — exactly 4 scenarios (minimum PR set,
  DEMOCI-06-002). The `jq 'select(.full_suite_only == false)'` filter correctly
  handles JSON booleans from `.github/demo-scenarios.json`.

**Push-to-main run** (run ID 32482959828, post #2448 merge):

- All 9 scenarios ran. `full_suite_only: true` entries included as expected.

Boolean coercion concern (CONCERN-2327) confirmed as not applicable to the
current `jq`-based implementation. AGENTS.md pitfall added (PR #2459).
