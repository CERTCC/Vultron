---
name: bugfix-skill-current-task-number-undefined
description: bugfix SKILL.md Phase 5 references CURRENT_TASK_NUMBER which is not defined in that scope
metadata:
  type: project
---

In `.agents/skills/bugfix/SKILL.md` Phase 5 (line 182), the bug escalation instruction says:

> Set `--parent "${CURRENT_TASK_NUMBER}"` so the bug is wired under the same task.

`CURRENT_TASK_NUMBER` is not defined anywhere in the Phase 5 context — only `ISSUE_NUMBER` (the issue being fixed) is in scope. An agent following Phase 5's instructions will either omit the `--parent` flag (creating an orphan bug) or incorrectly substitute `ISSUE_NUMBER`.

**Why:** Discovered during code review of #2604 (pre-existing, not introduced by that PR). Phase 1 captures the new bug number correctly; Phase 5 does not define an equivalent variable.

**How to apply:** When editing bugfix/SKILL.md Phase 5, replace `${CURRENT_TASK_NUMBER}` with `${ISSUE_NUMBER}` or add an explicit assignment `CURRENT_TASK_NUMBER=${ISSUE_NUMBER}` earlier in the phase.
