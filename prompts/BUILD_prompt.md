Objective: Complete the highest-priority pending implementation task.

1. Review Context

   - plan/PRIORITIES.md — current implementation priorities.
   - specs/*.md (start with specs/README.md) — authoritative requirements.
   - plan/IMPLEMENTATION_PLAN.md — current tasks and status.
   - plan/IMPLEMENTATION_NOTES.md — implementation notes and constraints.
   - notes/*.md (start with notes/README.md) — relevant lessons learned.

2. Select Work

   - Identify the highest-priority unchecked task in IMPLEMENTATION_PLAN.md.

3. Verify Before Coding

   - Search vultron/*and test/* to confirm current behavior.
   - Do not assume missing functionality; confirm via code search.
   - Handling missing prerequisites: If verification shows a blocking
     prerequisite, you MAY add at most one minimal prerequisite entry to
     `plan/IMPLEMENTATION_PLAN.md` under these constraints:
     - the addition is strictly necessary to complete the selected task and
       must be labeled `auto-added`
     - the entry must be a single line containing a short title, one-line
       justification, and a one-line acceptance criterion (e.g., "Done when <measurable>")
     - record rationale and any implementation notes in `plan/IMPLEMENTATION_NOTES.md`
     - commit the change with a message prefixed `plan: add prerequisite` and
       - include the selected-task id and the one-line justification
     - if more than one prerequisite is required or the change is
       non-trivial (affects design, scope, or more than one file), update
       `plan/IMPLEMENTATION_NOTES.md` with details and stop.
     - This exception is only for small, necessary prerequisites and does not
       authorize broader plan edits.

4. Implement

   - Implement only the selected task.
   - Follow project conventions.
   - Run validation commands specified in AGENTS.md.
   - If you encounter incidental bugs during implementation, add them to
     `plan/BUGS.md` with a clear description and reproduction steps, but do not
     pursue them unless they block the current task.

5. If Validation Succeeds

   - Mark the task complete in plan/IMPLEMENTATION_PLAN.md.
   - Update plan/IMPLEMENTATION_NOTES.md with relevant implementation details.
   - `git add` modified files and commit with a clear, specific message.

6. Exit. Only one task should be completed per run.

Constraints:

- Do not modify unrelated tasks.
- Do not skip validation.
- Each run operates in a fresh context.
