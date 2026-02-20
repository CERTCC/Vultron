1. Study specs/* to learn the application specifications.
2. Study plan/IMPLEMENTATION_PLAN.md to understand the current progress.
3. Study plan/IMPLEMENTATION_NOTES.md to understand any additional insights or observations that may be helpful for implementation.

- plan/IMPLEMENTATION_NOTES.md is ephemeral and meant to be reset periodically,
  so any critical insights in it need to be incorporated into either an AGENTS.
  md (specific technical instructions and tips), notes/*.md (insights about the
  design and implementation that are not specs), or the specs/*.md files 
  (refinements to the specifications based on lessons learned during 
  implementation).

4. Update AGENTS.md with any new insights or recommendations based on your 
   design review.
5. Update specs/* to refine any requirements that may be unclear, redundant, 
   or missing based on your review of the specifications, lessons learned, and implementation plan.

- Avoid over-specifying implementation details in the specifications; focus on what needs to be achieved rather than how it should be achieved.
- Follow existing formatting and style conventions in the specs/ directory.
- Ensure that each requirement is atomic, verifiable, and succinct.
- Remove or refactor any redundant requirements that appear in multiple files.

6. git commit changes with a clear commit message.

IMPORTANT: Write markdown files only.
Do NOT implement any code.
Do NOT assume functionality is missing; confirm with code search first.
