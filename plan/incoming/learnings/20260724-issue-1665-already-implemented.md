---
title: "Issue #1665 fully implemented by predecessor PR #1664 before build started"
type: learning
timestamp: "2026-07-24"
source: ISSUE-1665
signal: process-issue
---

Issue #1665 (CI linter enforcement of ECA format for DEMOMA scenario groups)
listed docs PR #1664 as a reference in the issue body. That PR was marked as
a "docs: plan" PR in its title, but it actually contained the full
implementation: `vultron/metadata/specs/lint.py` (`_check_scenario_start_groups`),
`specs/meta-specifications.yaml` (MS-13-004), `.github/workflows/spec-check.yml`,
and tests in `test/metadata/specs/test_lint.py`.

PR #1664 merged at 2026-07-24T15:32:52Z. The build session for #1665 started
after that merge, so all four ACs were already satisfied. Verified via grep and
`uv run pytest`. Issue closed with a reference comment.

**Pattern**: Issue bodies written during planning may reference a PR that is
framed as "docs/plan" but contains implementation. Check the actual files
touched by referenced PRs, not just the PR title prefix. See also
ISSUE-1612 (spec entries already present), ISSUE-1510 (feature already
implemented), ISSUE-1661 AC-4/AC-5 (pitfall entries added by blocker PR).
