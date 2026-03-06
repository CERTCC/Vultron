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
   - Study plan/BUGS.md - any known bugs that might impact implementation.

2. Perform Gap Analysis

   - Use search tools to compare specs/*against vultron/* and test/*.
   - Confirm implementation status via code search; do not assume missing functionality.
   - Identify mismatches, omissions, partial implementations, and untested behaviors.
   - Think rigorously and systematically.

   - Constraints: Do not attempt to verify, diagnose, or fix bugs here, just
     identify them as potential gaps and add them as tasks as appropriate in
     the next step.

3. Update plan/IMPLEMENTATION_PLAN.md

   - Based on your gap analysis, refine and revise the implementation plan.
   - Replace or refine content with a prioritized, bulleted task list.
   - Use markdown task format: `- [ ] Task description`.
   - Tasks must be atomic, actionable, testable, and unambiguous.
   - Tasks should be sized as "meaningful chunks": 
     - make each task large enough to produce measurable progress
       - (for example: implement a feature + tests + minimal docs or run a 
         one-off migration + tests)
     - but small enough to be completed in a single agent execution cycle.
     - Group closely related technical-debt items into a single task when  
       they share the same implementation context to reduce the number of  
       agent prompts required.
   - Order tasks by implementation priority.

4. Update plan/IMPLEMENTATION_NOTES.md

   - Items from the gap analysis that are not actionable tasks should be added as notes.
   - Add clarified assumptions, open questions, architectural concerns, and risks.
   - Record insights that will assist future agents.

5. Commit

   - Commit only modified plan files with a clear, specific commit message.

Constraints:

- Modify plan files only.
- Do NOT implement code.
- Do NOT speculate about missing functionality; verify with search first.
