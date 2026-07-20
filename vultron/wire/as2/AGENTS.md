# AGENTS.md — vultron/wire/as2/

> For project-wide conventions see the root
> [AGENTS.md](../../../AGENTS.md). This file covers rules specific to
> the ActivityStreams 2.0 wire layer: vocabulary classes, semantic
> extraction patterns, and outbound activity construction.

---

## Naming Conventions (wire layer)

- **All wire vocabulary class names** (base AS2 types AND Vultron-specific
  objects in `vultron/wire/as2/vocab/objects/`) MUST use the `as_` prefix.
  Examples: `as_Activity`, `as_Actor`, `as_VulnerabilityCase`,
  `as_CaseParticipant`, `as_CaseStatus`. See ARCH-14-001.
  - The wire base class is `as_VultronObject` (in `vocab/objects/base.py`).
    Do NOT use `VultronAS2Object` — that name is retired. See ARCH-14-002.
  - `TypeAlias` companion types also use the `as_` prefix:
    `as_VulnerabilityCaseRef`, `as_CaseParticipantRef`, etc. See ARCH-14-003.
  - **IMPORTANT**: Core domain models (`vultron/core/models/`) do NOT use the
    `as_` prefix. `VulnerabilityCase` (no prefix) is always the core type;
    `as_VulnerabilityCase` is always the wire type. If you find yourself
    importing `VulnerabilityCase` from `vultron.wire.as2.vocab.objects.*`,
    that is a bug — switch to `as_VulnerabilityCase`.
- **Wire-layer field names**: Use trailing underscore for fields whose
  plain name collides with a Python builtin or reserved word (e.g.,
  `id_`, `type_`, `object_`, `context_`) with a Pydantic alias for the
  JSON key (e.g., `id_: str = Field(alias="id")`). See CS-07-002,
  CS-07-003.
- **Do NOT use `as_`-prefixed field names** anywhere (the prefix is for
  class names only, not field or variable names).
- **Pattern objects**: Descriptive CamelCase with `Pattern` suffix
  (e.g., `CreateReportPattern`, `AcceptInviteToEmbargoOnCasePattern`)

---

## Semantic Extraction — Pattern Ordering Rules

`SEMANTIC_REGISTRY` in `vultron/semantic_registry/` is **order-sensitive**.
Specific patterns MUST precede general ones; `UNKNOWN` MUST be last. A
general pattern placed first silently shadows specific ones.

- `ActivityPattern` instances: `vultron/wire/as2/extractor/_instances.py`;
  re-exported from the package `__init__.py`
- Always `rehydrate()` before pattern matching
- Name pattern objects `<TypeName>Pattern`
- Test every new pattern in `test/test_semantic_activity_patterns.py`

Invariant: SE-03-002. `_validate_registry_order()` raises `RegistryOrderError`
at import time if violated.

See `notes/activitystreams-semantics.md` for full extractor design.

### Group ordering within `SEMANTIC_REGISTRY`

Entries are grouped by domain area; within each group, specific patterns
come before general ones:

| # | Group | Example semantics |
|---|---|---|
| 1 | Embargo events | `CREATE_EMBARGO_EVENT`, `INVITE_TO_EMBARGO`, `ACCEPT_INVITE_TO_EMBARGO` |
| 2 | Reports | `CREATE_REPORT`, `SUBMIT_REPORT`, `ACK_REPORT`, `VALIDATE_REPORT`, ... |
| 3 | Cases | `CREATE_CASE`, `UPDATE_CASE`, `ENGAGE_CASE`, `DEFER_CASE`, ... |
| 4 | Case membership | `INVITE_ACTOR_TO_CASE`, `ACCEPT_INVITE_ACTOR_TO_CASE`, ... |
| 5 | Case manager role | `OFFER_CASE_MANAGER_ROLE`, `ACCEPT_CASE_MANAGER_ROLE`, ... |
| 6 | Ownership transfer | `OFFER_CASE_OWNERSHIP_TRANSFER`, `ACCEPT_CASE_OWNERSHIP_TRANSFER`, ... |
| 7 | Case log entries | `ANNOUNCE_LOG_ENTRY`, `REJECT_LOG_ENTRY` |
| 8 | Vulnerability case announcements | `ANNOUNCE_VULNERABILITY_CASE` |
| 9 | Notes | `CREATE_NOTE`, `ADD_NOTE_TO_CASE`, `REMOVE_NOTE_FROM_CASE` |
| 10 | Participants | `CREATE_CASE_PARTICIPANT`, `ADD_CASE_PARTICIPANT`, ... |
| 11 | Fallback sentinels | `UNKNOWN_UNRESOLVABLE_OBJECT`, `UNKNOWN` |

When adding a new pattern, place it in the correct group. If it is more
specific than an existing entry in the same `activity_` group, place it
**before** that entry.

### Import-Time Order Guard

`_validate_registry_order()` is called at module load — a mis-ordered registry
**prevents the module from loading**. Also run
`test/test_semantic_activity_patterns.py` after any registry edit (belt-and-
suspenders for edge cases the runtime guard might miss).

### File Locations

| File | Role |
|---|---|
| `vultron/wire/as2/extractor/_pattern.py` | `ActivityPattern` class + `_match_activity_field` |
| `vultron/wire/as2/extractor/_instances.py` | All `*Pattern` instances |
| `vultron/wire/as2/extractor/_builders.py` | Field-extraction helpers + domain-object builders |
| `vultron/wire/as2/extractor/_extract.py` | `extract_intent` function |
| `vultron/wire/as2/extractor/__init__.py` | Public re-exports (backward-compat) |
| `vultron/semantic_registry/` | `SEMANTIC_REGISTRY`, `find_matching_semantics()`, `_validate_registry_order()` |
| `vultron/errors.py` | `RegistryOrderError(VultronError)` |
| `test/test_semantic_activity_patterns.py` | Pattern ordering + dispatch tests |

### Adding a New Pattern

1. Define `<TypeName>Pattern` in `_instances.py`.
2. Add to `extractor/__init__.py` re-export lists (import + `__all__`).
3. Add `SemanticEntry` in the correct group position.
4. Run `test/test_semantic_activity_patterns.py`.
5. If `RegistryOrderError`, move entry earlier than the conflicting general one.

---

## Constructing Outbound Activities

All outbound Vultron activities MUST be constructed via the factory
functions in `vultron.wire.as2.factories`. Code outside
`vultron/wire/as2/vocab/activities/` and `vultron/wire/as2/factories/`
MUST NOT import internal activity subclasses (e.g.,
`RmCreateReportActivity`) directly. Use the corresponding factory
function instead (e.g., `rm_create_report_activity()`). This boundary is
enforced by `test/architecture/test_activity_factory_imports.py`.

---

## Key Files Map — wire layer

- **Patterns**: `vultron/wire/as2/extractor/` — `ActivityPattern`
  class (`_pattern.py`) and `*Pattern` instance definitions
  (`_instances.py`); re-exported from the package `__init__.py`
- **Semantic Registry**: `vultron/semantic_registry/` — domain-split
  package; `SEMANTIC_REGISTRY` (ordered list),
  `find_matching_semantics()`, `use_case_map()`
- **Vocab Examples**: `vultron/wire/as2/vocab/examples/` — reference
  for message semantics and test fixtures
- **Factories**: `vultron/wire/as2/factories/` — canonical constructors
  for all outbound activities

---

## Common Pitfalls — wire layer

**`SEMANTIC_REGISTRY` ordering errors** — see pattern-ordering guidance above
and
[notes/activitystreams-semantics.md](../../../notes/activitystreams-semantics.md)
for all AS2 pitfalls (pattern matching, Union serialization, wire format vs.
domain model, `serialize_as_any=True`, rehydration, bootstrap activities, etc.).
