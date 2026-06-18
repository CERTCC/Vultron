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

`SEMANTIC_REGISTRY` in `vultron/semantic_registry/` is
**order-sensitive**. Specific patterns MUST appear before more general
ones. A pattern placed after a more general match will never be reached.

- `ActivityPattern` instances are defined in
  `vultron/wire/as2/extractor/_instances.py` and re-exported from
  `vultron/wire/as2/extractor/` (the package `__init__.py`); they are
  imported into the domain sub-modules under `vultron/semantic_registry/`
- Always `rehydrate()` on incoming activities before pattern matching
- Add new `ActivityPattern` objects named `<TypeName>Pattern`
- Test every new pattern in `test/test_semantic_activity_patterns.py`

See `notes/activitystreams-semantics.md` for the full extractor design.

### Overview

`SEMANTIC_REGISTRY` is the single ordered list that maps every AS2
activity structure to a `MessageSemantics` value, a `VultronEvent`
subclass, and a use-case class. `find_matching_semantics()` returns the
**first** match.

`ActivityPattern` objects — one per `MessageSemantics` value — are
defined in `vultron/wire/as2/extractor/_instances.py` and re-exported
from the `vultron/wire/as2/extractor/` package; they are imported into
the `semantic_registry` package submodules.

### The Ordering Invariant

**More-specific patterns MUST precede more-general ones. `UNKNOWN` must
be last.**

A pattern is *more specific* than another if its dump is a proper
superset of the other's dump within the same `activity_` group. If a
general pattern appears first, the specific one is never reached and the
wrong use case is invoked with no error signal.

This invariant is captured by `specs/semantic-extraction.yaml`
SE-03-002.

#### Group ordering within `SEMANTIC_REGISTRY`

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

Because a misplaced pattern fails silently at runtime,
`semantic_registry/__init__.py` calls
`_validate_registry_order(SEMANTIC_REGISTRY)` at module load time. If
any less-specific entry precedes a more-specific one within the same
`activity_` group, the validator raises `RegistryOrderError`
immediately on import.

This is a hard guard: a mis-ordered registry **prevents the module from
loading**, making the error impossible to miss.

#### Algorithm

The validator uses the same subset logic as
`test_non_overlapping_activity_patterns` in
`test/test_semantic_activity_patterns.py`:

1. Group entries by `activity_` type.
2. For every pair `(A, B)` where A appears before B in the registry:
   - if `dump(B)` is a strict subset of `dump(A)` (B is more specific),
     A should have appeared after B — raise `RegistryOrderError`.
3. Pass if no out-of-order pairs are found.

The test `test_non_overlapping_activity_patterns` is a
belt-and-suspenders check that also catches edge cases the runtime
validator might miss. Both should remain.

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

### Common Pitfall: Adding a Pattern Without Running Tests

When adding a new `ActivityPattern` to `extractor/_instances.py`:

1. Define the pattern object named `<TypeName>Pattern` in `_instances.py`.
2. Add the new name to the re-export lists in `extractor/__init__.py`
   (both the `from ... import` block and `__all__`).
3. Add the corresponding `SemanticEntry` in the correct group position.
4. Run `test/test_semantic_activity_patterns.py` immediately.
5. If import raises `RegistryOrderError`, move the new entry earlier in the
   registry before the more-general entry it conflicts with.

The runtime guard catches the common failure mode, and the test file provides
faster local feedback plus extra edge-case coverage.

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

**`SEMANTIC_REGISTRY` ordering errors fail silently —
`_validate_registry_order()` required** — see the pattern-ordering
guidance above.

A misplaced pattern (less-specific before more-specific within the same
`activity_` group) causes the wrong use case to execute with no error
signal. `_validate_registry_order()` raises `RegistryOrderError` at
import time to make this impossible to miss. Run
`test/test_semantic_activity_patterns.py` immediately after editing the
registry.

See [notes/activitystreams-semantics.md](../../../notes/activitystreams-semantics.md)
for:

- Pattern Matching with ActivityStreams
- `VulnerabilityCase.case_activity` Cannot Store Typed Activities
- Accept/Reject `object` Field Must Use an Inline Typed Activity Object
- Pydantic Union Serialization Silently Returns `None` for
  `active_embargo`
- ActivityStreams as Wire Format, Not Domain Model
- Preserve Subclass Identity in ActivityStreams Decorators
- Dead-Letter vs. No-Pattern: Two Distinct UNKNOWN Failure Modes
- Accept.object_ Must Be the Invite Activity, Not the Case Object
- Transitive Activity `object_` Contract at Base Type
- Base-Typed Serialization Drops Subtype Fields: Use
  `serialize_as_any=True`
- Invite Response Parsing Requires Recursive Rehydration
- Bootstrap Activities Must Embed Nested Objects Inline, Not as URI
  Strings
- Activity `name` Field Must Not Use `repr()` or `str()`
