---
title: bugfix SKILL.md Phase 5 references CURRENT_TASK_NUMBER which is not defined in that scope
type: learning
timestamp: "2026-08-27T00:00:00Z"
source: ISSUE-2604
signal: process-issue
---

In `.agents/skills/bugfix/SKILL.md` Phase 5 (line 182), the bug escalation instruction says:

> Set `--parent "${CURRENT_TASK_NUMBER}"` so the bug is wired under the same task.

`CURRENT_TASK_NUMBER` is not defined anywhere in the Phase 5 context — only `ISSUE_NUMBER` (the issue being fixed) is in scope. An agent following Phase 5's instructions will either omit the `--parent` flag (creating an orphan bug) or incorrectly substitute `ISSUE_NUMBER`.

Discovered during code review of #2604 (pre-existing in the skill file, not introduced by that PR).

**Fix:** When editing bugfix/SKILL.md Phase 5, replace `${CURRENT_TASK_NUMBER}` with `${ISSUE_NUMBER}` or add an explicit `CURRENT_TASK_NUMBER=${ISSUE_NUMBER}` assignment earlier in the phase.
