# Project Documentation Structure

**Status**: Draft  
**Created**: 2026-02-18  
**Last Updated**: 2026-02-18

## Purpose

This specification defines the purpose, scope, and maintenance requirements for
key project documentation files that guide AI agents and human developers.

---

## Documentation Files Overview

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
- Move completed phase details to IMPLEMENTATION_NOTES.md
- Add new phases as roadmap evolves
- Mark blockers as resolved when fixed

**Target Audience**: Agents planning next implementation steps

---

### plan/BT_INTEGRATION.md (Feature-Specific Plan)

**Purpose**: Detailed planning for specific feature (Behavior Tree integration).

**Scope** (MUST contain):
- Feature-specific architecture decisions
- Implementation phases for this feature
- Design constraints and requirements
- Integration points with existing code
- Testing strategy for this feature

**Scope** (MUST NOT contain):
- General project planning (belongs in IMPLEMENTATION_PLAN.md)
- Implementation lessons (belongs in IMPLEMENTATION_NOTES.md after work done)

**Maintenance**:
- Update as feature design evolves
- Archive when feature complete (move lessons to IMPLEMENTATION_NOTES.md)

**Target Audience**: Agents implementing this specific feature

---

## Content Migration Guidelines

When refactoring documentation:

1. **Status updates** → Move to IMPLEMENTATION_NOTES.md with date
2. **Lessons learned** → Move to IMPLEMENTATION_NOTES.md under relevant date
3. **Future priorities** → Move to IMPLEMENTATION_PLAN.md
4. **Technical gotchas** → Keep in AGENTS.md Common Pitfalls
5. **How-to guides** → Keep in AGENTS.md
6. **Design insights** → Move to IMPLEMENTATION_NOTES.md
7. **Specification issues** → Move to IMPLEMENTATION_NOTES.md

## File Size Guidelines

- **AGENTS.md**: Target < 800 lines (currently 1187 lines - needs reduction)
- **IMPLEMENTATION_NOTES.md**: No limit (grows over time)
- **IMPLEMENTATION_PLAN.md**: Target < 400 lines (archive completed phases)

---

## Cross-References

When one document references another:

- AGENTS.md MAY reference IMPLEMENTATION_NOTES.md for "see lessons learned"
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
