# Specification Style Guide (Concise)

## Purpose

Specification files define **atomic, testable requirements** for the project.
They must be concise, scannable, traceable, and suitable for automated or agent-assisted generation.

---

## File Structure

Files should be largely independent, each focusing on a specific topic of concern.
Requirements should be grouped by **category** and **priority** within each file.
Avoid extraneous maintenance overhead by avoiding boilerplate like counts or sources per requirement.

```markdown
# Specification Title

## Overview
Brief scope summary.

**Source**: Docs / ADRs  
**Note**: Optional scope clarifications

---

## Category (RFC 2119 LEVEL)
- `REQ-ID` Requirement statement
  - Optional clarifications
```

Rules:

* One divider (`---`) between header and requirements
* Group requirements by **category + priority**
* Keep formatting uniform across files

---

## Priority Levels (RFC 2119)

Use the RFC 2119 strength keyword **in every individual requirement line**,
not only in section headers. This enables automated extraction and filtering
of requirements by strength (e.g., `grep -E "MUST|SHOULD|MAY" specs/*.md`).

Accepted keywords:

* MUST / SHALL
* MUST NOT / SHALL NOT
* SHOULD
* SHOULD NOT
* MAY / OPTIONAL

Format — section header carries the dominant level for the group:

```markdown
## Category
```

Format — each requirement line carries its own keyword inline:

```markdown
- `IMPL-01-001` The system MUST use Python 3.13+
- `IMPL-01-002` Test fixtures SHOULD clean up after each test
- `IMPL-01-003` Log entries MAY include a correlation ID
```

---

## Requirement Format

* One requirement per bullet
* Single-sentence, imperative style with inline RFC 2119 keyword
* IDs required

```markdown
- `IMPL-01-001` The system MUST use Python 3.13+
```

Details:

* Use sub-bullets for constraints, thresholds, or rationale
* Limit nesting to 2–3 levels

---

## Requirement IDs

**Format**: `FILE_PREFIX-SECTION_#-###`

Rules:

* Sequential within file
* Stable (do not renumber; deprecate instead)
* Globally unique
* Always prefixed
* Requirement IDs should be stable and globally unique, but do not need to be sequential across files.
* Use prefixes at the file level and at the category level within files to aid traceability, uniqueness, and
  support future expansion without significant renumbering.
  E.g., EH-01-001, EH-01-002, EH-02-001, etc. where EH = error handling spec file,
  01 = category 1 (e.g., exception hierarchy), 02 = category 2 (e.g., error response format), etc.

Common prefixes:

* SYS, IMPL, TEST, PROTO
* RM, EM, CS
* BT-IMPL

---

## Writing Rules

* **Concise**: No prose explanations in requirements
* **Specific**: Avoid vague terms (“appropriate”, “robust”) unless defined
* **Testable**: Include measurable criteria where relevant
* **Declarative**: State *what*, not *how*, unless necessary

Use nested bullets for:

* Thresholds
* Exceptions
* Conditional applicability

---

## Organization Patterns

* Group by **domain first**, **priority second**
* Split MUST / SHOULD / MAY into separate sections if helpful
* Explicitly declare scope exclusions when relevant

Example patterns:

* Technology constraints
* Testing and quality gates
* Conditional or optional architecture
* Prototype vs production scope

---

## Sources and Cross-References

* Cross-references between specs MUST use the format `ID-1 relationship
ID-2` for cross references, where `relationship` is one of the relationship
  types below
  * e.g., `- XX-01-001 refines YY-01-002`
  * Following is a list of relationship types : inverse relationship types
    * refines : is-refined-by
    * derives-from : is-derived-by
    * implements : is-implemented-by
    * depends-on : is-dependency-of
    * conflicts-with : conflicts-with
    * supersedes : is-superseded-by
    * duplicates : is-duplicated-by
    * verifies : is-verified-by
    * part-of : has-part
    * constrains : is-constrained-by
    * extends : is-extended-by
  * Cross references MUST be included in the requirement as a sub-bullet
      for easy extraction
  * Cross-references SHOULD be placed in both the source and target
      requirements using the corresponding inverse relationship for
      bidirectional traceability
* Put sources **only in the header**, not per requirement
* Use inline links for cross-spec references
* **Consolidation notes**: Some specs consolidate requirements from multiple sources
  * `http-protocol.md` consolidates HTTP-related requirements from `inbox-endpoint.md`, `message-validation.md`, `error-handling.md`
  * `structured-logging.md` consolidates logging requirements from `observability.md`, `error-handling.md`, `inbox-endpoint.md`
  * Check file headers for "Consolidates:" notes indicating superseded requirements
* Record architectural decisions as ADRs when they affect:
  * Component boundaries
  * Persistence or protocol formats
  * Cross-cutting semantics (e.g., BT engines)

Minor refactors do **not** require ADRs.

---

## File Naming

* `kebab-case.md` for `notes/`, `specs/`, and `docs/adr/`
* `snake_case.md` for Diátaxis documentation (Tutorials, How‑to, Reference,
  Explanation) and most of `docs/`
* Descriptive, minimal
* Pattern: `{topic}-{type}.md` or `{topic}_{type}.md` depending on directory conventions

Examples:

* `notes/system_details.md`
* `specs/implementation-architecture.md`
* `specs/testing-requirements.md`
* `docs/reference/protocol_definition.md`

---

## Lifecycle of Superseded Requirements

When a requirement is superseded by a stronger or more complete replacement:

* **Remove** the old requirement from the spec file rather than marking it
  deprecated or leaving it in place with a "DEPRECATED" annotation.
* **Deprecated specs are agent noise.** Agents reading specs will act on
  whatever they find; a deprecated-but-still-present requirement may cause
  agents to comply with the wrong rule or generate confusion in discussions.
* **Record the removal** in `plan/IMPLEMENTATION_HISTORY.md` so there is an
  audit trail of what changed and why.
* **Update cross-references.** Any other spec or note that cited the removed
  requirement MUST be updated to point to the replacement.
* **Exception: "Stable IDs" rule applies to renumbering, not removal.** The
  "do not renumber" rule means existing IDs in git history remain traceable;
  it does not mean dead requirements must stay in the file forever.

---

## Quality Criteria

A good specification is:

* **Scannable** (priority-grouped)
* **Traceable** (stable IDs)
* **Testable** (verifiable criteria)
* **Maintainable** (low formatting overhead)

---

Use this guide as the **normative baseline** for all Vultron specifications.
