## Objective

Refine, create, and organize specification and design documentation so that repository documentation is concise, consistent, testable, and aligned with current priorities and design direction.

---

## Constraints

1. Modify **markdown files only** (e.g., `specs/`, `docs/`, `notes/`, `plan/`, `AGENTS.md`).
2. **Do not modify code or tests.**
3. **Verify assumptions against the codebase before asserting missing functionality.**
   - Search the codebase to confirm whether functionality exists.
   - Do not assume absence without evidence.

---

## 1. Review Repository Context

Study the following to understand the current state of the project.

1. `plan/PRIORITIES.md` — current priorities.
2. `docs/adr/*.md` — architectural decisions and rationale.
3. `specs/` — authoritative requirements.
4. `plan/IDEAS.md` — proposed ideas and potential future work.
5. `plan/IMPLEMENTATION_PLAN.md` — current implementation roadmap.
6. `plan/IMPLEMENTATION_HISTORY.md` — completed implementation tasks.
7. `plan/IMPLEMENTATION_NOTES.md` — recent insights and design observations (ephemeral).
8. `notes/` — durable design insights, lessons learned, and open questions.
9. `AGENTS.md` — agent guidance and process rules.
10. `vultron/` — current codebase.
11. `test/` — test implementation and coverage.

Important:

- `IDEAS.md` and `IMPLEMENTATION_NOTES.md` are **ephemeral** and may be reset.
- Any critical insight contained in those files **must be preserved elsewhere**.

---

## 2. Analyze Documentation

Perform a gap and consistency analysis across documentation.

Identify:

1. Missing requirements.
2. Ambiguous requirements.
3. Redundant or contradictory requirements.
4. Drift from current priorities.
5. Architectural inconsistencies.

Specifically check for:

- Items in `PRIORITIES.md`, `IDEAS.md`, or `IMPLEMENTATION_NOTES.md` not yet reflected in:
  - `specs/`
  - `notes/`
  - `AGENTS.md`
- Duplicate or conflicting material across `specs/` and `notes/`.

When analyzing `IDEAS.md` and `IMPLEMENTATION_NOTES.md`:

1. Do **not** assume existing specs fully capture their content.
2. Compare carefully to ensure all insights and nuances are preserved.
3. Do **not** reference these files from durable documentation since they may be wiped.

---

## 3. Refine Specifications (`specs/`)

Improve requirements documentation.

1. Clarify, split, merge, or remove requirements as needed.
2. Requirements must be:
   - atomic
   - specific
   - concise
   - verifiable
3. `specs/` are for *what*, not *how*. Avoid prescribing implementation details.
4. Eliminate redundancy across spec files.
5. Organize one-topic-per-file where helpful.
6. Use the `PROD_ONLY` tag for production-only requirements.
7. Update `specs/README.md` to reflect:
   - added files
   - removed files
   - renamed files
   - reorganized topics.

---

## 4. Update Design Notes (`notes/`)

Maintain durable architectural knowledge.

1. Capture:
   - design insights
   - architectural observations
   - tradeoffs
   - lessons learned
2. Do **not** duplicate specification text.
3. Promote critical insights from `IMPLEMENTATION_NOTES.md`.
4. Clearly mark unresolved items:

Example formats:

- `Open Question: ...`
- `Design Decision: ...`

When applicable, indicate dependencies:

- `Design Decision: (blocks ITEM-ID)`
- `Open Question: (blocked-by ITEM-ID)`

5. Update `notes/README.md` when files are added, removed, or reorganized.

---

### 5. Capture specific implementation plan tasks

If specific implementation tasks are identified that are not already 
captured in `plan/IMPLEMENTATION_PLAN.md`:

1. Add them to `plan/IMPLEMENTATION_PLAN.md` with a clear description  and 
   any relevant details, creating new sections if needed.
2. Ensure they are appropriately prioritized relative to existing tasks.
3. Do **not** add implementation tasks that are too vague or high-level; 
   they must be specific enough to be actionable and testable.
4. `IMPLEMENTATION_PLAN.md` is for **implementation tasks only** (the *how*);
   do not add design insights, open questions, or general notes to this file.

---

## 5. Update Agent Guidance (`AGENTS.md`)

Add or refine recurring implementation guidance.

Requirements:

1. Guidance must be:
   - precise
   - actionable
   - minimal
2. Document recurring patterns, conventions, or process rules useful for future agents.

---

## 6. Preserve Ephemeral Insights

For items originating in:

- `IDEAS.md`
- `IMPLEMENTATION_NOTES.md`

that have been captured elsewhere:

1. Apply **line-level strikethrough** to the specific completed or migrated lines in the original file.
2. Immediately add a short note referencing where the material now lives.

Example:
```markdown
~~Original idea text~~
→ captured in specs/foo.md
```


Rules:

- The **entire line or paragraph must be struck through**, not just a header.
- Do **not** delete the original text.
- Ensure no important insight remains only in these ephemeral files.

---

## 7. Ensure Documentation Consistency

Across all modified files ensure:

1. Consistent formatting and style.
2. Valid Markdown syntax.
3. Lint compliance (e.g., `markdownlint`).
4. `specs/README.md` lists all spec files.
5. `notes/README.md` lists all notes files.

After modifying requirements or terminology:

1. Run repository-wide text searches for affected keywords.
2. Remove or reconcile obvious duplicates or outdated references.

If a requirement conflict cannot be resolved:

1. Add an item to `plan/IMPLEMENTATION_NOTES.md` summarizing:
   - the conflict
   - file paths
   - relevant excerpts
2. **Stop before committing changes.**

---

## 8. Commit Changes

1. Commit **markdown-only** changes.
2. Use clear, specific commit messages.
3. Use multiple commits if changes are thematically distinct.

Examples:

- spec refactoring
- insights promoted from IMPLEMENTATION_NOTES
- AGENTS.md guidance updates

---

## Final Rule

**DO NOT MODIFY ANY CODE.**  
This prompt applies **only to markdown documentation.**