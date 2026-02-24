# Project Documentation Structure

## Overview

This specification defines the purpose, scope, and maintenance requirements for
key project documentation files that guide AI agents and human developers.

---

## Documentation Files Overview

### docs/adr/*.md (Architectural Decision Records)

**Purpose**: Capture architectural decisions, their rationale, and alternatives
considered.

**Format**: MADR (Markdown Any Decision Records) with optional YAML front matter.
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
- Implementation phases with clear tasks
- Dependency ordering (what must be done before what)
- Acceptance criteria for each phase
- Blockers and open questions
- Future work priorities
- Current phase status (high-level only)

**Scope** (MUST NOT contain):
- Detailed debugging history (belongs in IMPLEMENTATION_NOTES.md)
- Lessons learned (belongs in IMPLEMENTATION_NOTES.md)
- Technical how-tos (belongs in AGENTS.md)
- Completed work details (summarize and move to IMPLEMENTATION_NOTES.md)

**Maintenance**:
- Update phase status as work progresses
- Move completed phase details to `plan/IMPLEMENTATION_NOTES.md`
- Add new phases as roadmap evolves 
- Mark blockers as resolved when fixed
- `PD-02-001` Prior task history SHOULD be moved out of  
  `plan/IMPLEMENTATION_PLAN.md` into the append-only
  `plan/IMPLEMENTATION_HISTORY.md` archive to keep the active plan concise
  - Create `plan/IMPLEMENTATION_HISTORY.md` if it does not exist

**Target Audience**: Agents planning next implementation steps

---

## Content Migration Guidelines

When refactoring documentation:

1. **Status updates** → Move to IMPLEMENTATION_NOTES.md with date
2. **Lessons learned** → Move to IMPLEMENTATION_NOTES.md under relevant date
3. **Future priorities** → Move to IMPLEMENTATION_PLAN.md
4. **Technical gotchas** → Keep in AGENTS.md Common Pitfalls
5. **How-to guides** → Keep in AGENTS.md
6. **Durable design insights** → Move to notes/*.md (topic-specific file)
7. **Ephemeral design context** → Move to IMPLEMENTATION_NOTES.md
8. **Specification issues** → Move to IMPLEMENTATION_NOTES.md

## File Size Guidelines

- **AGENTS.md**: Target < 1000 lines; prioritize clarity and scannability
  - Use directory-specific AGENTS.md files if needed to keep content focused and concise
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
- IMPLEMENTATION_NOTES.md SHOULD reference relevant specs and ADRs
- IMPLEMENTATION_PLAN.md SHOULD reference spec requirements
- All documents MAY reference specs/ for authoritative requirements

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
