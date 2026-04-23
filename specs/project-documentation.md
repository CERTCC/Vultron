# Project Documentation Structure

## Overview

This specification defines the purpose, scope, and maintenance requirements for
key project documentation files that guide AI agents and human developers.

---

## Documentation Files Overview

### docs/adr/*.md (Architectural Decision Records)

**Purpose**: Capture architectural decisions, their rationale, and alternatives
considered.

**Format**: MADR (Markdown Any Decision Records) with optional YAML front
matter.
A template is available at `docs/adr/_adr-template.md`.

**Front matter fields** (optional but encouraged):

- `status`: proposed | rejected | accepted | deprecated | superseded by
  (link to new ADR)
- `date`: YYYY-MM-DD when the decision was last updated
- `deciders`: list of people involved in the decision
- `consulted`: subject-matter experts consulted (two-way communication)
- `informed`: people kept up-to-date on progress (one-way communication)

**Scope** (MUST contain):

- Title describing the decision (short, problem + solution form)
- Context and Problem Statement
- Considered Options (at least two)
- Decision Outcome (chosen option with justification)

**Scope** (SHOULD contain):

- Decision Drivers
- Consequences (positive and negative)
- Pros and Cons of each option

**Scope** (MAY contain):

- Validation criteria (how to verify compliance with the decision)
- Non-Goals
- More Information (links to related ADRs, team agreements,
  re-evaluation criteria)

**Maintenance**:

- Create a new ADR for each significant architectural decision
- Use `docs/adr/_adr-template.md` as the starting point
- Number sequentially (e.g., `0009-next-decision.md`)
- Mark superseded ADRs with `status: superseded by [ADR-XXXX](link)`
- Do not delete superseded ADRs; preserve the historical record

**Target Audience**: Developers and agents needing context on why key
architectural decisions were made

### notes/*.md (Design Insights)

**Purpose**: Capture durable design insights, domain-specific guidance, and
lessons learned that are expected to remain relevant over time. Unlike
`plan/IMPLEMENTATION_NOTES.md` (which is ephemeral and may be wiped), files
in `notes/` are committed to version control and MUST be kept up to date as
the implementation evolves.

**Current files**:

- `notes/bt-integration.md`: Behavior tree design decisions, py_trees
  patterns, simulation-to-prototype strategy
- `notes/activitystreams-semantics.md`: Activity model, state-change
  notification semantics, response conventions
- `notes/README.md`: Index and conventions for the notes directory

**Scope** (MUST contain):

- Design and implementation insights expected to remain relevant over time
- Domain-specific guidance for future agents and developers
- Cross-references to relevant specs and ADRs
- Architectural patterns and the rationale behind them

**Scope** (MUST NOT contain):

- Implementation status or progress tracking (belongs in
  IMPLEMENTATION_NOTES.md)
- Future planning or prioritization (belongs in IMPLEMENTATION_PLAN.md)
- Ephemeral debugging history (belongs in IMPLEMENTATION_NOTES.md)
- Technical how-tos or quick-reference content (belongs in AGENTS.md)

**Maintenance**:

- Update with new insights or observations from design reviews that are not
  specific technical instructions or refinements to the specifications
- When a lesson is learned during implementation, add it here as durable
  guidance (not only in `plan/IMPLEMENTATION_NOTES.md`)
- Retain indefinitely — these files serve as a long-term resource for
  future agents to learn from past experiences and insights
- Each file focuses on a specific topic area; create new files for
  distinct topics
- Cross-reference from `AGENTS.md` where relevant
- **`notes/README.md` MUST be updated** whenever a file is added to or
  removed from `notes/`, or when a file's scope changes significantly
- **`archived_notes/README.md` MUST be updated** whenever a file is moved
  to `archived_notes/` — record the archiving date, reason, and any
  rescued items
- Files MUST be added to `notes/README.md` in the same commit as the file
  itself; do not add files without a corresponding README entry

**Target Audience**: Future agents and developers needing durable design
context and domain-specific guidance

---

### AGENTS.md (Technical Reference)

**Purpose**: Quick technical reference for AI agents working in the repository.

**Scope** (MUST contain):

- Quick start checklist (essential commands, file locations)
- Technology stack and approved tools
- Architectural constraints (layer separation, import rules)
- Handler protocol and registry pattern (technical how-to)
- Coding rules (naming conventions, validation, type safety)
- Quick reference sections (adding message types, key files map)
- Commit workflow tips
- Common pitfalls (technical gotchas: circular imports, data layer
  signatures, test data patterns)
- Specification usage guidance (how to read and reference specs)

**Scope** (MUST NOT contain):

- Implementation status or progress tracking
- Lessons learned about architectural decisions
- Design review findings or insights
- Implementation planning or prioritization
- Detailed debugging history

**Maintenance**:

- Update when technical patterns change
- Update when new pitfalls discovered
- Keep concise and scannable
- Focus on "how" not "why" or "what's done"

**Target Audience**: AI agents needing quick technical guidance

---

### plan/IMPLEMENTATION_NOTES.md (Lessons Learned)

**Purpose**: Capture lessons learned, architectural insights, and debugging
history from implementation work.

**Scope** (MUST contain):

- Lessons learned from implementation (what worked, what didn't)
- Architectural decisions and rationale
- Debugging history with root cause analysis
- Design review findings and insights
- Performance measurements and optimization notes
- Implementation status snapshots (with dates)
- Production readiness assessments
- Known specification issues and workarounds

**Scope** (MUST NOT contain):

- Quick reference information (belongs in AGENTS.md)
- Future planning (belongs in IMPLEMENTATION_PLAN.md)
- Coding how-tos (belongs in AGENTS.md)
- Implementation history or 'what was done' summaries from build cycles
  (belongs in IMPLEMENTATION_HISTORY.md)

**Maintenance**:

- Add dated entries as work progresses
- Include context: what was tried, what failed, why
- Link to relevant commits, PRs, specs
- Preserve history (don't delete old entries)
- Organize by date or topic (use headers)

**Target Audience**: Future implementers needing context on past decisions

---

### plan/IMPLEMENTATION_PLAN.md (Forward Planning)

**Purpose**: Define implementation roadmap, phases, and future work.

**Scope** (MUST contain):

- Pending, in-progress, and blocked tasks only
- Dependency ordering (what must be done before what)
- Acceptance criteria for each task
- Blockers and open questions

**Scope** (MUST NOT contain):

- Detailed debugging history (belongs in IMPLEMENTATION_NOTES.md)
- Lessons learned (belongs in IMPLEMENTATION_NOTES.md)
- Technical how-tos (belongs in AGENTS.md)
- Completed tasks in any form — completed tasks belong exclusively in
  `plan/IMPLEMENTATION_HISTORY.md`
- Tombstone entries, "done" markers, or completed-task summaries; once a task
  is complete it is deleted from the PLAN entirely

**Maintenance**:

- Update phase status as work progresses
- Move completed phase details to `plan/IMPLEMENTATION_HISTORY.md`
- Implementation insights go to `plan/IMPLEMENTATION_NOTES.md` (not here)
- Add new phases as roadmap evolves
- `plan/PRIORITIES.md` is the authoritative source of priority ordering
- Section order in `plan/IMPLEMENTATION_PLAN.md` MAY group related work by
  topic or execution context and MUST NOT override `plan/PRIORITIES.md` when
  the two conflict
- Task Sizing Guidance (SHOULD)
  - Tasks listed in `plan/IMPLEMENTATION_PLAN.md` SHOULD be sized as
     "meaningful chunks":
    - Make each task large enough to produce measurable progress (for
       example: implement a feature with tests and a minimal documentation
       note; or run a one-off migration including tests), but small enough
       to be completed in a single agent execution cycle (one agent run or
       one focused human work session).
    - Rationale: grouping many very small plan items increases overhead
       for agents and reviewers (more prompts, more context switches).
       Overly large tasks become hard to reason about, validate, and track.
       "Meaningful chunks" balance visibility, atomicity, and execution
       efficiency.
    - When a change requires multiple distinct implementation contexts
       (separate services or major refactors), split it into separate
       tasks. When multiple small fixes share the same implementation
       context (same module, tests, or PR), group them into one task.
  - Minimal acceptance criteria for a task:
    - A clear, testable definition of "done" (e.g., tests to add/modify
       and expected behaviours).
    - Any blocking dependencies (phases/tasks that must complete first).
    - A short note about scope (one sentence) to avoid ambiguity.
  - Examples:
    - Anti-pattern (too tiny): `- [ ] Fix one failing assert in
       test_foo.py`
    - Good ("meaningful chunk"): `- [ ] Fix failing test suite for module
       foo: update validation, add edge-case tests, and document behavior in
       docs/foo.md`
    - Anti-pattern (too large): `- [ ] Rewrite the entire data layer and
       update all docs`
    - Better (split by context): `- [ ] Refactor tinydb backend to
       DataLayer protocol + tests` and `- [ ] Update demo scripts and docs
       to use refactored DataLayer`
  - Guidance for reviewers/agents:
    - Prefer tasks that can be completed and validated in a single PR.
    - If a proposed task will require multiple agent prompts or multiple
       distinct PRs, break it into smaller contextual subtasks and record
       the parent/child relationship in the plan.
- Phases get a Unique ID tag (e.g., `DEMO-1`)
  - Steps within a phase get hierarchical tags (e.g., `DEMO-1.1`, `DEMO-1.2`)
  - Individual task items within a step get further tags (e.g., `DEMO-1.1.1`)
    to allow precise tracking and referencing, also allowing additions or
    deletions of task items within a step to be less disruptive to the overall
    numbering scheme
- Mark blockers as resolved when fixed
- `PD-02-001` Completed task history MUST be stored exclusively in the
  append-only `plan/IMPLEMENTATION_HISTORY.md` archive.
  - Create `plan/IMPLEMENTATION_HISTORY.md` if it does not exist.
  - `plan/IMPLEMENTATION_HISTORY.md` is **append-only**: entries are never
    edited, updated, or deleted once written.
- `PD-02-002` *(superseded)* — The tombstone one-liner format is **abolished**.
  See PD-02-003 through PD-02-006 for the replacement rules.
- `PD-02-003` **Core Invariant**: A task in DONE state MUST NOT exist in PLAN
  in any form — not as a checked item, not as a tombstone, not as a one-liner
  summary.
- `PD-02-004` **Atomic Completion**: Completing a task is a two-phase atomic
  operation: (1) append the completed task record to
  `plan/IMPLEMENTATION_HISTORY.md`, then (2) delete the task from
  `plan/IMPLEMENTATION_PLAN.md`. Both steps MUST happen together — a task
  MUST NOT remain in PLAN after its HISTORY entry is written.
- `PD-02-005` **No Tombstones**: Completed tasks MUST be removed entirely from
  `plan/IMPLEMENTATION_PLAN.md`. No tombstone entries, ~~strikethrough~~
  items, `[x]` checkboxes, or "→ see HISTORY" one-liners are permitted.
- `PD-02-006` **Bounded Plan**: `plan/IMPLEMENTATION_PLAN.md` SHOULD contain
  no more than 20 active tasks at any time. When new work is identified,
  either add it as a pending task (removing a lower-priority item if needed)
  or queue it externally.

**Target Audience**: Agents planning next implementation steps

---

### `plan/IMPLEMENTATION_HISTORY.md` (Completed Implementation Archive)

**Purpose**: Archive completed implementation phases from
`IMPLEMENTATION_PLAN.md` for historical reference. Also captures deferred
'future work' that was deprioritized but may be relevant later.

**Scope** (MUST contain):

- Completed implementation phases with details on what was done, when, and how
- Per-build 'what was done' summaries appended after each implementation cycle
- Deferred future work that was deprioritized (with rationale and context)
- Commit references where relevant pointing to completed work

**Maintenance**:

- When an implementation phase is completed, move its details from
  `IMPLEMENTATION_PLAN.md` to `IMPLEMENTATION_HISTORY.md`
- Treat `IMPLEMENTATION_HISTORY.md` as an append-only archive; do not delete or
  modify past entries
- Include context for deferred future work to explain why it was deprioritized
  and any conditions under which it might be revisited

## Content Migration Guidelines

When refactoring documentation:

1. **Status updates** → Move to IMPLEMENTATION_NOTES.md with date
2. **Completed phases / 'what was done' summaries** → Append to IMPLEMENTATION_HISTORY.md
3. **Lessons learned** → Move to IMPLEMENTATION_NOTES.md under relevant date
4. **Future priorities** → Move to IMPLEMENTATION_PLAN.md
5. **Technical gotchas** → Keep in AGENTS.md Common Pitfalls
6. **How-to guides** → Keep in AGENTS.md
7. **Durable design insights** → Move to notes/*.md (topic-specific file)
8. **Ephemeral design context** → Move to IMPLEMENTATION_NOTES.md
9. **Specification issues** → Move to IMPLEMENTATION_NOTES.md

## File Size Guidelines

- **AGENTS.md**: Target < 1000 lines; prioritize clarity and scannability
  - Use directory-specific AGENTS.md files if needed to keep content focused
      and concise
- **notes/*.md**: No strict limit per file; create new files for distinct topics
- **IMPLEMENTATION_NOTES.md**: No limit (grows over time)
- **IMPLEMENTATION_PLAN.md**: Target < 400 lines (archive completed phases)
- **IMPLEMENTATION_HISTORY.md**: No limit (archive of past completed
  implementation details)
- `PD-01-001` Large modules with multiple responsibilities SHOULD be refactored
  into smaller cohesive modules
  - When proposed refactors affect architecture, consider raising an ADR and
      document the change in `docs/adr/`

---

## Cross-References

When one document references another:

- AGENTS.md SHOULD NOT reference IMPLEMENTATION_NOTES.md for "see lessons
  learned" because the content is expected to be ephemeral and may be wiped,
  instead:
  - AGENTS.md MAY reference notes/*.md for "see lessons learned and design
      insights"
- notes/*.md MUST reference relevant specs and ADRs
- docs/adr/*.md SHOULD cite specs, notes, or implementation history for
  durable rationale and SHOULD NOT rely on IMPLEMENTATION_NOTES.md as the only
  long-lived reference for an architectural point
- IMPLEMENTATION_NOTES.md SHOULD reference relevant specs and ADRs
- IMPLEMENTATION_PLAN.md SHOULD reference spec requirements
- All documents MAY reference specs/ for authoritative requirements

---

## Documentation Currency

- `PD-03-001` `notes/*.md` files MUST be updated when implementation phases
  they describe are completed
  - Forward-looking statements such as "not yet implemented" MUST be
    replaced with historical references (e.g., "implemented in Phase X")
    once the described work is done
- `PD-03-002` (SHOULD) `notes/*.md` files that are purely historical and contain no
  durable design guidance SHOULD be archived in `docs/archived_notes/` with
  a brief rationale, rather than deleted
- `PD-03-003` Module paths referenced in `notes/` MUST be updated to
  reflect canonical current locations whenever those paths change
  - `plan/IMPLEMENTATION_HISTORY.md` is the authoritative record of *when*
    changes occurred; the active source code is the authoritative record of
    *where* components are currently located
  - Developers MUST confirm component locations via a code search rather
    than relying solely on historical notes; notes referencing old paths
    MUST be updated to reflect the current canonical location

---

## Rationale

**Problem**: AGENTS.md grew to 1187 lines, mixing quick reference with
implementation status, design insights, and planning. This makes it hard for
agents to quickly find technical guidance.

**Solution**: Separate concerns:

- Technical how-to stays in AGENTS.md (quick reference)
- Historical context and lessons go to IMPLEMENTATION_NOTES.md (deep dive)
- Future planning goes to IMPLEMENTATION_PLAN.md (roadmap)

**Benefits**:

- Agents can quickly scan AGENTS.md for technical patterns
- Historical context preserved in IMPLEMENTATION_NOTES.md for deep analysis
- Planning discussions stay focused in IMPLEMENTATION_PLAN.md

---

## Documentation Build Validation

- `PD-04-001` (MUST) `mkdocs build --strict` MUST pass without warnings
  before any changes to `docs/` directory files are staged for commit
  - The `--strict` flag treats all warnings (broken links, missing anchors,
    invalid markdown) as errors that prevent the build from completing
  - Common failure causes:
    - Broken anchor links: `#section-name` references that do not exist in
      the target document
    - Missing files: links to documentation files that have been deleted or
      moved without updating references
    - Invalid markdown: syntax errors that prevent proper rendering
- `PD-04-002` Validation MUST occur after markdown linting (via
  `.github/skills/format-markdown/SKILL.md`) and before test runs, in the
  build-and-test workflow documented in `.github/skills/build-docs/SKILL.md`
- `PD-04-003` (SHOULD) Agents SHOULD run `uv run mkdocs build --strict`
  locally when modifying `docs/` files to catch issues before staging for
  commit, reducing CI failures and improving development velocity
