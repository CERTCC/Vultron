# Guidance for agents working in `specs/`

> These rules are scoped to the `specs/` directory.
> See the root `AGENTS.md` for project-wide rules.
>
## Specification-Driven Development

This project uses formal specifications in `specs/` directory defining testable
requirements.

### Loading Specifications

**Always run `uv run spec-dump` before any implementation or design task.**
This produces flat, inheritance-resolved JSON covering all 48 spec files. Raw
`specs/*.yaml` files are for authoring and linting only — do not read them
directly. See `.agents/skills/load-specs/SKILL.md` for field definitions and
usage guidance.

### Working with Specifications

- Each spec defines requirements with unique IDs (e.g., `HP-01-001`)
- Requirements use RFC 2119 keywords: MUST, SHOULD, MAY
- Each requirement has verification criteria
- Implementation changes SHOULD reference relevant requirement IDs
- Some specs consolidate requirements from multiple sources; check the `tags`
  field and `edges` array for cross-references

### Key Specifications

See `specs/README.md` for the full index organized by topic. Key groups:

- **Cross-cutting**: `http-protocol.yaml`, `structured-logging.yaml`,
  `idempotency.yaml`, `error-handling.yaml`
- **Handler pipeline**: `inbox-endpoint.yaml`, `message-validation.yaml`,
  `semantic-extraction.yaml`, `dispatch-routing.yaml`, `handler-protocol.yaml`
- **Quality**: `testability.yaml`, `observability.yaml`, `code-style.yaml`
- **BT integration**: `behavior-tree-integration.yaml`

Always load cross-cutting specs (`ARCH`, `CS`, `TB`, `HP`, `SL`, `EH`) even
when working on a narrow feature — they impose constraints on all code.

### Test Coverage Requirements

- **80%+ line coverage overall** (per `specs/testability.yaml`)
- **100% coverage for critical paths**: message validation, semantic
  extraction, dispatch routing, error handling
- Test structure mirrors source structure
- Tests named `test_*.py` in parallel directories

---

## Specification Usage Guidance

### Reading Specifications

- Requirements use RFC 2119 keywords: **MUST**, **SHOULD**, **MAY**
- Each requirement has a unique ID (e.g., `HP-01-001`)
- **Cross-references** link related requirements across specs
- **Verification** sections show how to test requirements
- **Implementation** notes suggest approaches (not mandatory)

### When Specifications Conflict

If requirements appear to conflict:

1. Check **cross-references** in the `edges` array from `uv run spec-dump`
2. Consolidated specs (`http-protocol.yaml`, `structured-logging.yaml`) take
   precedence over older inline requirements
3. MUST requirements override SHOULD/MAY
4. Ask for clarification rather than guessing

### Updating Specifications

When updating specs per LEARN_prompt instructions:

- **Avoid over-specifying implementation details**: Specify *what*, not *how*
- **Keep requirements atomic**: One testable requirement per ID
- **Remove redundancy**: Use cross-references instead of duplicating
  requirements
- **Maintain verification criteria**: Every requirement needs a test
- **Follow existing conventions**: Match style and structure of other specs

**Do NOT add spec entries for** (route to `AGENTS.md` instead):

- File paths, module locations, or package layouts (e.g., "factory functions
  MUST live in `vultron/wire/as2/factories/`")
- Demo scenario step ordering, file layout, or script structure
- Agent or skill behavior instructions (e.g., "the agent MUST confirm the
  selected bug with the user")
- Naming conventions already enforced by `code-style.yaml`
- Coding practices or conventions internal to this Python codebase

**Gate test before adding to `specs/`**: Ask "Would a participant running a
different implementation of the Vultron protocol notice if this requirement
were violated?" If **no**, the requirement is an internal convention — route
it to `AGENTS.md`, not `specs/`. This test operationalizes MS-05-004
(declarative requirements) and the four-tier taxonomy (MS-12): if it fails
the protocol or architecture tier tests, it belongs in `project` or `process`
kind — and if it also fails the externally-visible test, it belongs in
`AGENTS.md` rather than specs at all.

---

### Valid `kind:` Values

The `kind:` field accepts exactly four values:

```text
protocol  architecture  project  process
```

`implementation` is **NOT** valid and causes spec-lint to reject the file at
commit time. The error may look like a YAML syntax error — it is not.

- Use `kind: protocol` for external protocol obligations (what a Vultron
  participant must do on the wire).
- Use `kind: architecture` for structural constraints on the system (layering,
  import rules, module boundaries).
- Use `kind: project` for internal project conventions that do not affect
  external protocol behavior.
- Use `kind: process` for development process rules (testing, documentation,
  CI).

Check existing entries in the same spec file for context before writing a new
entry. *Source: ISSUE-2258*

---

### Valid `priority:` Values — Underscores, Not Spaces

The `priority:` field enum uses **underscores**: `MUST_NOT`, `SHOULD_NOT`.
**Not spaces.** MS-02-002 prose writes "MUST NOT" with a space, but the Pydantic
validator enum uses underscores. Using `MUST NOT` (space) breaks spec-lint with
a FATAL registry load error.

Valid values:

```text
MUST  MUST_NOT  SHOULD  SHOULD_NOT  MAY
```

<!-- Source: ISSUE-2393 -->

---

### Valid `rel_type` Values in Spec Relationships

When adding a `relationships:` entry to a spec requirement, `rel_type` MUST be
one of the enumerated values validated by `SpecFile`. Using an invalid value
causes a Pydantic `ValidationError` at `spec-dump` time.

**Valid `rel_type` values:**

```text
implements, supersedes, extends, depends_on, conflicts, refines,
derives_from, verifies, part_of, constrains, satisfies
```

`related_to` is **NOT** valid. If the intent is a loose relationship, use
`refines` with a clarifying `note:` field, or omit the relationship entirely
if no normative link exists.

---

### Specification Quick Links

See `specs/` directory for detailed requirements with testable verification
criteria.

---
