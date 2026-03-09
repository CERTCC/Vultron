## Objective

Refine, create, and organize specification and design
documentation so the repository's specs, notes, and agent guidance are  
concise, testable, and aligned with the project's current priorities and ideas.

## Tasks

### Primary constraints

- Modify markdown files only (e.g., files under specs/, docs/, notes/, AGENTS.md)
- Do not modify code or tests.
- Verify assumptions by searching the codebase before asserting missing
  functionality or gaps. Do not assume functionality is missing without  
  confirming by searching the codebase for evidence.

### Study and understand current state of the project

1. Study `plan/PRIORITIES.md` to understand current priorities
2. Study `docs/adr/*.md` to understand past architectural decisions and their
   rationales
3. Study `specs/` to understand current requirements
4. Study `plan/IDEAS.md` to understand new ideas that are not yet incorporated
5. Study `plan/IMPLEMENTATION_PLAN.md` and `plan/IMPLEMENTATION_HISTORY.md` to
   understand the current implementation status
6. Study`notes/` to understand lessons learned, design tradeoffs, and open 
   questions
7. Study `plan/IMPLEMENTATION_NOTES.md` to understand current open questions, design
   insights, and implementation constraints
8. Study AGENTS.md to understand current agent guidance and process rules 
9. Study `vultron/` to understand the current codebase
10. Study `test/` to understand current test implementation and coverage

### Analyze gaps, ambiguities, and redundancies across documentation

1. Perform a gap analysis to identify gaps, ambiguities, and redundancy
   across `specs/` and `notes/`
   1. Potential gaps include:
      1. Items in `PRIORITIES.md`, `IDEAS.md`, `IMPLEMENTATION_NOTES.md`
         that are not yet reflected in `specs/`, `notes/`, or `AGENTS.md` 
      2. Items in `specs/` or `notes/` that are contradictory or redundant
   2. `IDEAS.md` and `IMPLEMENTATION_NOTES.md` are ephemeral and
      will be reset periodically, these items MUST be captured elsewhere.
      1. Any critical insights or design ideas from those files should go into 
         `specs/` or `notes/` as appropriate.
      2. When analyzing gaps especially with respect to items in IDEAS.md and  
         IMPLEMENTATION_NOTES.md, ensure that all the salient points in these
         documents are included in the analysis to ensure that they are covered
         in the refined `specs/` and `notes/` documentation.
      3. Do not assume that just because an item in `IDEAS.md` or
         IMPLEMENTATION_NOTES.md already has a matching item in `specs/` or  
         `notes/` that it is fully captured, as new insights or nuance may have
         been added to expand an existing item in the `specs/` or `notes/`  
         documentation. Instead, carefully analyze the content of the items
         to ensure that all critical insights and design ideas are captured  
         in specs/ or`notes/` as appropriate.
      4. `specs/` and `notes/` MUST not have references to `IDEAS.md` or  
         `IMPLEMENTATION_NOTES.md` since the files might be wiped or reset, 
         leaving broken references and missing critical information.

### Refine and organize documentation

1. Review `specs/project-documentation.md` to understand the structure and 
   purpose of the documentation in the repository, including the
   distinction between `specs/`, `notes/`, and `AGENTS.md` and the intended
   content for each.
2. Refine `specs/` to clarify, split, merge, or remove requirements as needed.
   1. Ensure each requirement is atomic, specific, concise, and verifiable.
   2. Avoid prescribing implementation details in specs; focus on what must be achieved, not how.
   3. Use `PROD_ONLY` tag for requirements that only apply to production.
   4. Organize `specs/` into one topic-per-file where that improves clarity.
   5. Update `specs/README.md` to reflect any changes to content in spec 
      files, or files added, removed, or renamed.
3. Refine`notes/` to capture critical insights, design tradeoffs, and open
   questions that are not yet reflected in `specs/`.
   1. Ensure notes are concise and focused on insights rather than
      requirements (which would be captured in `specs/`).
   2. Use notes to document design exploration, tradeoffs, and TODOs that
      are not testable requirements.
      1. Clearly mark any open questions or unresolved design decisions
         with a consistent format e.g., "Open Question: ..."; "Design
         Decision:". When applicable, indicate whether such items are
         blocked or are blockers themselves. e.g., "Design decision: (blocks ITEM-ID)";
         "Open Question: (blocked-by ITEM-ID)".
   3. Update`notes/README.md` to reflect any changes in `notes/` files
4. Refine `AGENTS.md` to update any recurring agent guidance or process rules as needed.
   1. Ensure guidance is precise, actionable, terse, and minimal.

### Ensure quality, consistency, and alignment across documentation

1. Ensure quality and consistency across modified files, including:
   1. Consistent formatting and style
   2. Proper use of markdown syntax for readability
      1. use markdownlint or markdownlint-cli for automated linting
   3. Confirm that `specs/README.md` lists all spec files and points to top-level categories
   4. Confirm that`notes/README.md` lists all notes files and points to top-level categories
   5. For items in `IDEAS.md` and `IMPLEMENTATION_NOTES.md` that have been
      captured elsewhere
      1. mark them with ~~strikethrough~~ and
      2. add a note in the original location in `IDEAS.md` or `IMPLEMENTATION_NOTES.md`
         with a reference to where they have been captured in `specs/` or
        `notes/` or `AGENTS.md` where applicable.
      3. DO NOT LEAVE important content behind in `IDEAS.md` or 
         `IMPLEMENTATION_NOTES.md` without capturing it elsewhere, these 
         files are ephemeral.
2. Propagate changes across files as needed to maintain consistency and
   alignment with current priorities and ideas. For example, if you clarify
   a requirement in `specs/`, check if there are related `notes/` that also
   need to be updated to reflect the clarified requirement or any design
   insights related to it.
   1. Run a repository-wide text search for the keywords that motivated
      changes (e.g., old requirement names) and ensure no obvious leftover
      duplicates.
3. If you cannot resolve a conflicting requirement or you suspect an
   upstream policy change is required, draft an item summarizing the conflict
   with evidence (file paths and short excerpts) , add it to 
   `IMPLEMENTATION_NOTES.md`, and STOP before committing.
4. You are not required to run tests for markdown-only edits.

### Finalize and commit changes

1. Git add and commit changes with a clear commit message.
   1. Multiple commits are appropriate if there are multiple thematically distinct
      changes (e.g., refactoring redundant requirements in one commit,
      incorporating new insights from `IDEAS.md` and `IMPLEMENTATION_NOTES.md`
      into `specs/` in another commit, and updating `AGENTS.md` in a third commit).
2. EXIT

DO NOT MODIFY ANY CODE. This prompt is only for modifying markdown files.
