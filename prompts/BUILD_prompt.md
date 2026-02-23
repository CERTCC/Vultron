Objective: Complete the highest-priority pending implementation task.

1. Review Context
   - plan/PRIORITIES.md — current implementation priorities.
   - specs/*.md (start with specs/README.md) — authoritative requirements.
   - plan/IMPLEMENTATION_PLAN.md — current tasks and status.
   - plan/IMPLEMENTATION_NOTES.md — implementation notes and constraints.
   - notes/*.md (start with notes/README.md) — relevant lessons learned.

3. Select Work
   - Identify the highest-priority unchecked task in IMPLEMENTATION_PLAN.md.

4. Verify Before Coding
   - Search vultron/* and test/* to confirm current behavior.
   - Do not assume missing functionality; confirm via code search.

5. Implement
   - Implement only the selected task.
   - Follow project conventions.
   - Run validation commands specified in AGENTS.md.

6. If Validation Succeeds
   - Mark the task complete in plan/IMPLEMENTATION_PLAN.md.
   - Update plan/IMPLEMENTATION_NOTES.md with relevant implementation details.
   - `git add -A`
   - Commit with a clear, specific message.
   - Exit

Constraints:
- Do not modify unrelated tasks.
- Do not skip validation.
- Each run operates in a fresh context.
