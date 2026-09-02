---
title: Filing an issue is not the same as deferring the fix
type: learning
timestamp: "2026-09-02T00:00:00+00:00"
source: ISSUE-2958
signal: theme-candidate
---

When a code-review finding lands in a file your PR didn't touch, the right
response is **file an issue AND fix it now** — not file an issue as a substitute
for fixing it.

Filing is a tracking action. Fixing is the actual work. The decision to file
(so the finding isn't lost) is separate from the decision about timing (do it
now vs. a future PR). A finding that is size:S and clearly scoped should be done
immediately unless it would break the PR's coherence or require its own test
infrastructure.

**Why:** Parking a trivial fix in the backlog guarantees a second session
rediscovers and re-reasons about it, paying the context cost twice. Filing felt
like tracking it; it wasn't — it was postponing it. Several of the 8 findings
from PR #3078's code review were one-liners that should have been applied in the
same session rather than queued.

**How to apply:** When the upward-reflection checklist fires BW-07-009 (findings
in untouched files must be filed as issues), also ask: is this fix trivially
small? If yes, apply it now and close the issue in the same PR. Filing without
fixing is only correct when the fix is non-trivial, requires its own tests, or
would substantially change the PR's character.
