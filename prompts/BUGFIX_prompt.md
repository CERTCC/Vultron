Objective: Fix the highest-priority open bug using test-first development.

1. Review Context
   - specs/* (start with specs/README.md) — authoritative requirements.
   - plan/IMPLEMENTATION_PLAN.md — current task status.
   - plan/IMPLEMENTATION_NOTES.md — prior implementation notes.
   - plan/BUGS.md — known bugs (BUGS.md supersedes the implementation plan).
   - notes/*.md (start with notes/README.md) — relevant lessons learned.

2. Select Work
   - Choose the highest-priority open bug in plan/BUGS.md.

3. Verify Before Changes
   - Search vultron/*and test/* to confirm current behavior.
   - Do not assume the bug exists without verification.

4. Reproduce with a Failing Test
   - Add or modify a test in tests/* that fails due to the bug.
   - Confirm the test fails before implementing the fix.

5. Implement the Fix
   - Modify code only as required to resolve the bug.
   - Run validation commands specified in AGENTS.md.

6. Iterate
   - If tests fail, continue refining the fix until all relevant tests pass.
   - Do not proceed until validation succeeds.
   - If you encounter additional bugs during implementation, add them to 
     `plan/BUGS.md` with a clear description and reproduction steps, but do not
     pursue them unless they are the highest-priority open bug.

7. Finalize
   - Mark the bug fixed in plan/BUGS.md.
   - Update plan/IMPLEMENTATION_NOTES.md with relevant details.
     - include a summary of the issue, root cause, and how it was resolved.
     - include notes about other bugs encountered if applicable.
     - include notes of architectural or design implications if applicable
   - git add and commit changes with a clear, specific message.

Constraints:

- Follow test-first discipline.
- Do not work on implementation-plan tasks while bugs remain.
- Each run starts in a fresh context.
