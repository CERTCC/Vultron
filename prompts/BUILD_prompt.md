Objective: Complete the highest-priority pending implementation task.

## Review Context

1. study plan/PRIORITIES.md to understand current implementation priorities.
2. study specs/*.md (start with specs/README.md) to understand authoritative 
   requirements.
3. study plan/IMPLEMENTATION_PLAN.md to understand current tasks and status.
4. study plan/IMPLEMENTATION_NOTES.md to understand recent lessons learned 
   and constraints.
5. study notes/*.md (start with notes/README.md) to understand other relevant 
     lessons learned.
6. study vultron/* and test/* to understand current implementation and behavior.

## Select Work

6. Identify the highest-priority unchecked task in IMPLEMENTATION_PLAN.md.

   - If multiple small or trivial tasks are available, at the current 
     priority level, you may complete more 
     than one in the same run to conserve build iterations and 
     context-switching.
   - `PRIORITIES.md` is authoritative for priority order, but task ordering 
     may need to account for prerequisites, blockers, and dependencies. 
   - Task ordering in IMPLEMENTATION_PLAN.md is a rough guide but not 
     authoritative, use judgment to select the most valuable task(s) that 
     can be completed in a single run.

## Verify Before Coding

7. Search vultron/* and test/* to understand current implementation current 
   behavior. Do not assume missing functionality; confirm via code search.

8. Handling missing prerequisites: If verification shows a blocking
   prerequisite, you MAY add at most one minimal prerequisite entry to 
   `plan/IMPLEMENTATION_PLAN.md` under these constraints:

     - the addition is strictly necessary to complete the selected task and
       must be labeled `auto-added`
     - the entry must contain a short title, one-line justification, and a 
       one-line acceptance criterion (e.g., "Done when <measurable>")
     - record rationale and any implementation notes in `plan/IMPLEMENTATION_NOTES.md`
     - commit the change with a message prefixed `plan: add prerequisite` and
       include the selected-task id and the one-line justification

9. If more than one prerequisite is required or the change is
  non-trivial (affects design, scope, or more than one file), update
  `plan/IMPLEMENTATION_NOTES.md` with details and stop.

10. This exception is only for small, necessary prerequisites and does not
    authorize broader plan edits.

## Implement

11. Implement only the selected task.
   - Follow project conventions.
   - If you added an incidental prerequisite, you may address it in 
     the same changeset
   - You may use sub-agents for implementation, but validation tests must be 
     run by the main agent to ensure the task is fully complete before validation.

## Validate

12. Run validation commands specified in AGENTS.md.

    - This must be performed by the main agent, even if sub-agents were used 
      for implementation.
    - Do not skip or delegate validation.

13. If you encounter incidental bugs during implementation, add them to
  `plan/BUGS.md` with a clear description and reproduction steps, but do not
  pursue them unless they block the current task.

14. If Validation Succeeds

    - Mark the task complete in plan/IMPLEMENTATION_PLAN.md.
    - Append a 'what was done' summary to plan/IMPLEMENTATION_HISTORY.md;  
      record any lessons learned or constraints in plan/IMPLEMENTATION_NOTES.md.
    - `git add` modified files and commit with a clear, specific message.

## Exit

15. Exit.

    - Only one task (or set of trivial tasks) should be completed per run.

## Constraints

- Do not modify unrelated tasks.
- Do not skip validation.
- Each run operates in a fresh context.
