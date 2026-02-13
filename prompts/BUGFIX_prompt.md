1. Study specs/*
2. Study plan/IMPLEMENTATION_PLAN.md and plan/IMPLEMENTATION_NOTES.md to understand the current progress and any notes.
3. Study plan/BUGS.md to understand the current known bugs and their status.
4. Pick the most important bug to fix.
5. Search the codebase before making changes ("don't assume not implemented").
6. Implement the fix and run the validation commands found in AGENTS.md.
7. If tests fail, repeat steps 5-6 until they pass. Do not proceed to step 8 until all relevant tests pass.
8. If tests pass
   1. update plans/IMPLEMENTATION_PLAN.md (mark task done),
   2. update plans/IMPLEMENTATION_NOTES.md with any relevant notes about the implementation
   3. git add -A,
   4. and git commit with a description.
9. Exit. Every iteration must start with a fresh context.
