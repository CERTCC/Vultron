Objective: Refine specifications and technical guidance based on current design,
priorities, and lessons learned.

1. Review Context
    - Study specs/* — authoritative requirements.
    - Study plan/PRIORITIES.md — current priorities.
    - Study plan/IDEATION.md — new ideas and proposals.
    - Study plan/IMPLEMENTATION_PLAN.md — implementation status.
    - Study plan/IMPLEMENTATION_HISTORY.md — completed tasks.
    - Study notes/*.md — durable lessons learned.
    - Study plan/IMPLEMENTATION_NOTES.md — recent, ephemeral insights.

   Note: Critical insights in IMPLEMENTATION_NOTES.md must be preserved
   elsewhere.

2. Synthesize
    - Identify requirement gaps, ambiguity, redundancy, drift from priorities,
      and architectural inconsistencies.
    - Confirm assumptions against the codebase before concluding functionality
      is missing.
      - search, don't assume not implemented.

3. Update AGENTS.md
    - Add precise technical guidance and recurring implementation patterns.
    - Focus on actionable instructions for future agents.

4. Refine specs/*
    - Clarify, split, merge, or remove requirements as needed.
    - Keep requirements atomic, verifiable, and succinct.
    - Avoid prescribing implementation mechanics.
    - Eliminate redundancy across spec files.
    - Follow existing formatting and style conventions.

5. Update notes/*.md
    - Capture durable design insights and architectural observations.
    - Do not duplicate spec text.
    - Promote critical insights from IMPLEMENTATION_NOTES.md as appropriate.

6. Commit
    - Commit markdown changes only.
    - Use a clear, specific commit message.

Constraints:

- Modify markdown files only.
- Do not implement code.
- Verify assumptions via code search before asserting gaps.
