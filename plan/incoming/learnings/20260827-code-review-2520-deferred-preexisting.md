---
title: Code review of docs PR for #2520 surfaced 7 pre-existing bugs in unrelated files
type: learning
timestamp: 2026-08-27
source: ISSUE-2520
signal: deferred-bug
---

During code review for PR implementing #2520 (case model explanation docs), the
reviewer diffed `main...HEAD` against a stale local `main` and surfaced 10 findings
across files changed by other PRs. None are in files touched by this PR. Disposition:

**Already tracked / intentional design (no new issue needed):**

- `build/SKILL.md:272` — CURRENT_TASK_NUMBER undefined
  → learning `20260827-bugfix-skill-current-task-number-undefined.md`
- `bt_node.py:277` — fixname() ignores child prefix-map override
  → learning `20260827-mermaid-prefix-map-rendering-scope.md` — INTENTIONAL DESIGN
- `actor.py:223` — backend.update() without setup()
  → learning `20260827-code-review-2109-deferred-preexisting.md` item #1

**New findings — GitHub issues created as part of this DEFER:**

- `inbox_pipeline.py:133` — transient VultronValidationError permanently dropped;
  behavioral split with production inbox_handler → Bug #2766
- `case_proposal.py:318` — RejectCaseProposal raises VultronValidationError caught
  as permanent failure, Reject activity silently lost → Bug #2767
- `sync.py:244` — race: auth writes entry between two sequential fetches causes
  spurious assertion failure → Bug #2768
- `polling.py:1368` + `:1349` — inner except swallows construction failures;
  [0] access without guard → Bug #2769
- `plan-issue/SKILL.md:275` — annotation inside --body heredoc posted verbatim
  as part of GitHub issue body → Concern #2770
- `bugfix/REFERENCE.md:75` — PARENT_ARG unquoted; word-splits if ISSUE_NUMBER
  empty → Concern #2771
