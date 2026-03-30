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
   - Remove any existing priority labels (low, medium, high, etc.) or 
     numbers from tasks, as priorities may have changes since the last 
     update. Use plan/PRIORITIES.md coupled with your analysis of task 
     dependencies to determine the order of tasks in the list, but do not 
     include explicit priority labels in the task descriptions themselves. 
     A later build step will be responsible for prioritizing tasks at build 
     time.
   - Completed task details should be moved to IMPLEMENTATION_HISTORY.md 
     leaving a short one-three line summary reference in IMPLEMENTATION_PLAN.md 
     for each moved item (or moved section if an entire block of 
     related tasks was completed)

4. Update plan/IMPLEMENTATION_NOTES.md

    a. Capture existing items into notes files
     - Items that were converted from IMPLEMENTATION_NOTES.md to 
     IMPLEMENTATION_PLAN.md tasks should be removed from 
     IMPLEMENTATION_NOTES.md.
    - Items from the gap analysis that are not actionable tasks should be 
     added to `notes/` files as needed, and removed from 
     IMPLEMENTATION_NOTES.md once they are fully captured in `notes/` files.
    - Often, the details in notes are relevant so avoid over-compressing 
     summaries and information loss when moving items to the notes files. 
     For task conversion, ensure that relevant notes details are captured in 
     the notes files in addition to the task description where appropriate.
   b. Add new observations to IMPLEMENTATION_NOTES.md
    - Add clarified assumptions, open questions, architectural concerns, and risks.
    - Record insights that will assist future agents.

5. Commit

   - Commit only modified plan files with a clear, specific commit message.

Constraints:

- Modify plan files only.
- Do NOT implement code.
- Do NOT speculate about missing functionality; verify with search first.
