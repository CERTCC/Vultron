Objective: Update the implementation plan based on current priorities, specifications, code, and tests.

1. Review Context

   - Study plan/PRIORITIES.md — current implementation priorities.
   - Study specs/* — authoritative application specifications.
   - Study plan/IMPLEMENTATION_PLAN.md — current task status.
   - Study plan/IMPLEMENTATION_HISTORY.md — completed tasks.
   - Study notes/*.md — lessons learned and prior insights.
   - Study plan/IMPLEMENTATION_NOTES.md — open questions and observations.
   - Study vultron/* — codebase.
   - Study test/* — existing tests.

2. Perform Gap Analysis

   - Use search tools to compare specs/*against vultron/* and test/*.
   - Confirm implementation status via code search; do not assume missing functionality.
   - Identify mismatches, omissions, partial implementations, and untested behaviors.
   - Think rigorously and systematically.

4. Update plan/IMPLEMENTATION_PLAN.md
   
   - Replace or refine content with a prioritized, bulleted task list.
   - Use markdown task format: `- [ ] Task description`.
   - Tasks must be atomic, actionable, testable, and unambiguous.
   - Order tasks by implementation priority.

5. Update plan/IMPLEMENTATION_NOTES.md
   
   - Add clarified assumptions, open questions, architectural concerns, and risks.
   - Record insights that will assist future agents.

6. Commit
   
   - Commit only modified plan files with a clear, specific commit message.

Constraints:

- Modify plan files only.
- Do NOT implement code.
- Do NOT speculate about missing functionality; verify with search first.
