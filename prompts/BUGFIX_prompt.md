1. Study specs/* (hint: start with specs/README.md) to learn the application specifications.
2. Study plan/IMPLEMENTATION_PLAN.md and plan/IMPLEMENTATION_NOTES.md to understand the current progress and any notes.
3. Study plan/BUGS.md to understand the current known bugs and their status.
4. Study notes/*.md as needed for any relevant lessons learned (hint: start with notes/README.md).
6. Pick the most important bug to fix.
7. Search the codebase before making changes ("don't assume not implemented").
8. Write a test that fails due to the bug.
   1. This may involve writing a new test or modifying an existing one.
   2. The test should be added to the appropriate test file in tests/*.
9. Implement the fix and run the validation commands found in AGENTS.md.
10. If tests fail, repeat steps 5-7 until they pass. Do not proceed to step 9 until all relevant tests pass.
11. If tests pass
    1. update plans/BUGS.md (mark bug as fixed),
    2. update plans/IMPLEMENTATION_NOTES.md with any relevant notes about the implementation
    3. git add -A,
    4. and git commit with a description.
12. Exit. Every iteration must start with a fresh context.
