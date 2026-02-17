1. Study specs/*
2. Study plan/IMPLEMENTATION_PLAN.md and plan/IMPLEMENTATION_NOTES.md to understand the current progress and any notes.
3. Study plan/BUGS.md to understand the current known bugs and their status.
4. Pick the most important bug to fix.
5. Search the codebase before making changes ("don't assume not implemented").
6. Write a test that fails due to the bug. 
   1. This may involve writing a new test or modifying an existing one. 
   2. The test should be added to the appropriate test file in tests/*.
7. Implement the fix and run the validation commands found in AGENTS.md.
8. If tests fail, repeat steps 5-7 until they pass. Do not proceed to step 9 until all relevant tests pass.
9. If tests pass
   1. update plans/BUGS.md (mark bug as fixed),
   2. update plans/IMPLEMENTATION_NOTES.md with any relevant notes about the implementation
   3. git add -A,
   4. and git commit with a description.
10. Exit. Every iteration must start with a fresh context.
