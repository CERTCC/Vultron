---
title: "AC-4 and AC-5 were already implemented before #1661 was worked"
type: learning
timestamp: "2026-07-24"
source: ISSUE-1661
signal: process-issue
---

Issue #1661 specified two AGENTS.md pitfall entries as ACs (AC-4 in
`vultron/core/AGENTS.md` and AC-5 in `vultron/demo/AGENTS.md`). Both were
already present when the issue was worked — they had been added as part of
the #1653 PR that was listed as the blocker for #1661.

The issue body was written before #1653 landed; the pitfall entries were
added as part of that PR's finalization rather than deferred to this issue.

**How to apply:** Before assuming an AC requires writing new content, read the
current state of the target file. AGENTS.md pitfall entries added by blocker
PRs will often already satisfy ACs in the follow-on task. See also the earlier
instance of this pattern: ISSUE-1612 AC-5 (spec entries already present),
ISSUE-1510 (feature already implemented).
