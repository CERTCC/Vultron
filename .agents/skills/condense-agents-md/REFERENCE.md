# Condense AGENTS.md — Reference

## Categorization Heuristics

Use these questions to classify a section:

1. **Is it essential orientation that every agent needs on every task?**
   → `KEEP` (e.g., Purpose, Quickstart, Scope, Safety & Guardrails,
   Quick Reference, Project Vocabulary)

2. **Does it govern a specific subdirectory?**
   → `MOVE` to that directory's AGENTS.md
   - Testing rules → `test/AGENTS.md`
   - Spec authoring/usage rules → `specs/AGENTS.md`
   - Wire/AS2 conventions → `vultron/wire/AGENTS.md`

3. **Is it a pitfall write-up with a matching notes/ file?**
   → `REF:notes/x.md` — check `notes/` for obvious matches first:

   | Topic | Notes file |
   |---|---|
   | BT pitfalls (blackboard, cascade, anti-pattern) | `notes/bt-integration.md` |
   | ActivityStreams semantics (wire format, Accept/Reject, name field) | `notes/activitystreams-semantics.md` |
   | Case state model (case_status list, CaseEvent timestamps) | `notes/case-state-model.md` |
   | Architecture / layer separation | `notes/architecture-ports-and-adapters.md` |
   | Domain model separation | `notes/domain-model-separation.md` |
   | Codebase structure (actor IDs, demo lifecycle) | `notes/codebase-structure.md` |
   | DataLayer design | `notes/datalayer-design.md` |
   | History management | `notes/history-management.md` |

4. **Is it a pitfall with no notes/ home?**
   → `NEW-NOTE:notes/x.md` — create a new notes/ file with the canonical
   write-up, then treat as `REF`.

---

## Default Migration Map (Vultron root AGENTS.md)

| Section | Default action |
|---|---|
| Purpose | KEEP |
| Agent Quickstart | KEEP (trim to ~30 lines; move "Essential commands" to REF) |
| Scope of Allowed Work | KEEP |
| Technology Stack | KEEP (trim; move tool versions to a note if they drift) |
| Architectural Constraints | REF:notes/architecture-ports-and-adapters.md |
| Agent Guidance / Vultron-Specific Architecture | REF:notes/architecture-ports-and-adapters.md |
| Semantic Message Processing Pipeline | REF:notes/architecture-ports-and-adapters.md |
| Hexagonal Architecture | REF:notes/architecture-ports-and-adapters.md |
| Protocol Activity Model | REF:notes/activitystreams-semantics.md |
| Use-Case Protocol | KEEP (it's a mandatory checklist, keep short version) |
| Registry Pattern | KEEP (short) |
| Layer Separation | REF:notes/architecture-ports-and-adapters.md |
| Protocol-Based Design | KEEP (short) |
| Background Processing | KEEP (short) |
| Error Hierarchy | KEEP (short) |
| Coding Rules / Naming Conventions | KEEP |
| Validation and Type Safety | KEEP |
| Decorator Usage | KEEP (2 lines) |
| Code Organization | KEEP (short) |
| Markdown Formatting | KEEP (short) |
| Logging Requirements | KEEP (short) |
| Specification-Driven Development | MOVE:specs/AGENTS.md |
| Working with Specifications | MOVE:specs/AGENTS.md |
| Key Specifications | MOVE:specs/AGENTS.md |
| Test Coverage Requirements | MOVE:test/AGENTS.md |
| Testing Expectations (all sub-sections) | MOVE:test/AGENTS.md |
| Quick Reference / Adding a New Message Type | KEEP |
| Quick Reference / Key Files Map | KEEP |
| Quick Reference / Specification Quick Links | MOVE:specs/AGENTS.md |
| Change Protocol | KEEP |
| Commit Workflow | KEEP (or REF to build skill) |
| Specification Usage Guidance | MOVE:specs/AGENTS.md |
| Safety & Guardrails | KEEP |
| Project Vocabulary | KEEP |
| Default Behavior | KEEP |
| Common Pitfalls: Circular Imports | REF:notes/codebase-structure.md |
| Common Pitfalls: Pattern Matching / ActivityStreams | REF:notes/activitystreams-semantics.md |
| Common Pitfalls: Test Data Quality | MOVE:test/AGENTS.md |
| Common Pitfalls: BT (all BT sub-sections) | REF:notes/bt-integration.md |
| Common Pitfalls: Health Check Readiness Gap | NEW-NOTE:notes/codebase-structure.md |
| Common Pitfalls: Docker Health Check | NEW-NOTE:notes/codebase-structure.md |
| Common Pitfalls: FastAPI response_model | NEW-NOTE:notes/codebase-structure.md |
| Common Pitfalls: Idempotency Responsibility Chain | KEEP (short) |
| Common Pitfalls: case_activity Cannot Store Typed Activities | REF:notes/activitystreams-semantics.md |
| Common Pitfalls: Accept/Reject object field | REF:notes/activitystreams-semantics.md |
| Common Pitfalls: Pydantic Union / active_embargo | REF:notes/activitystreams-semantics.md |
| Common Pitfalls: case_status Is a List | REF:notes/case-state-model.md |
| Common Pitfalls: CaseEvent Trusted Timestamps | REF:notes/case-state-model.md |
| Common Pitfalls: ActivityStreams as Wire Format | REF:notes/activitystreams-semantics.md |
| Common Pitfalls: Preserve Subclass Identity | REF:notes/activitystreams-semantics.md |
| Common Pitfalls: Black + pyright suppressions | NEW-NOTE:notes/codebase-structure.md |
| Common Pitfalls: filterwarnings | MOVE:test/AGENTS.md |
| Common Pitfalls: Pytest Helper Enums | MOVE:test/AGENTS.md |
| Common Pitfalls: Avoid BaseModel in Ports | REF:notes/architecture-ports-and-adapters.md |
| Common Pitfalls: Activity name Field | REF:notes/activitystreams-semantics.md |
| Common Pitfalls: Actor IDs Must Be Full URIs | REF:notes/codebase-structure.md |
| Common Pitfalls: BT Failure Reason | REF:notes/bt-integration.md |
| Common Pitfalls: Dead-Letter vs No-Pattern | REF:notes/activitystreams-semantics.md |
| Parallelism and Single-Agent Testing | MOVE:test/AGENTS.md |
| Skill Interaction Rules | KEEP |
| Governance note for agents | KEEP |
| Miscellaneous tips | KEEP (trim; move long sub-sections) |
| Notes frontmatter maintenance | KEEP |
| Docs links must be relative | KEEP (short) |
| Demo script lifecycle logging | REF:notes/codebase-structure.md |
| Archiving IMPLEMENTATION_PLAN.md | KEEP (short) |
| Writing project history entries | KEEP |

---

## New notes/ File Frontmatter Template

```yaml
---
title: "Short descriptive title"
status: active
related_specs:
  - SPEC-ID-001
related_notes:
  - notes/related-file.md
---
```

Required fields: `title`, `status`. Optional: `related_specs`, `related_notes`.

---

## Per-Directory AGENTS.md Rules

- Keep per-directory files under **200 lines**.
- Start with a one-line purpose statement: `# Guidance for agents working in <directory>/`
- Do not duplicate content from the root AGENTS.md — link to it instead.
- If a per-directory file grows beyond 200 lines, apply this skill recursively.
