1. Study plans/IDEATION.md to understand new ideas in the project.
2. Study specs/*.md to understand the current specifications.
3. Study plan/PRIORITIES.md to understand the current priorities for the project.
4. Review plan/IMPLEMENTATION_PLAN.md to understand the current implementation status and technical debt.
5. Identify any gaps in the current specifications that need to be filled to support the new ideas and priorities.
6. Generate a comprehensive list of specifications that align with the project intent.
7. Ensure each specification is atomic, verifiable, and succinct.
8. Organize the specifications into logical categories or files as appropriate.
   1. One file per topic of concern.
   2. Use the PROD_ONLY tag to indicate any requirements that are only relevant
      for production and not for prototype development or testing.
9. Avoid redundancy by ensuring each requirement appears only once.
10. Update specs/README.md to reflect the actual set of specification files.
11. Items in plans/IDEATION.md that do not rise to the level of a 
    specification should be documented in notes/*.md as appropriate with 
    cross-references to related specifications for traceability.
    1. If notes/*.md files are added or updated, be sure to update the 
       notes/README.md if necessary to reflect the actual set of notes files.
12. git commit the new specifications and notes with a clear commit message.
