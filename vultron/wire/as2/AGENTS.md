# AGENTS.md — vultron/wire/as2/

> For project-wide conventions see the root
> [AGENTS.md](../../../AGENTS.md). This file covers rules specific to
> the ActivityStreams 2.0 wire layer: vocabulary classes, semantic
> extraction patterns, and outbound activity construction.

---

## Naming Conventions (wire layer)

- **ActivityStreams class names**: Use `as_` prefix (e.g., `as_Activity`,
  `as_Actor`) — in this layer (`vultron/wire/as2/`) **only**. Do NOT use
  `as_`-prefixed field names anywhere.
- **Wire-layer field names**: Use trailing underscore for fields whose plain
  name collides with a Python builtin or reserved word (e.g., `id_`,
  `type_`, `object_`, `context_`) with a Pydantic alias for the JSON key
  (e.g., `id_: str = Field(alias="id")`). See CS-07-002, CS-07-003.
- **Pattern objects**: Descriptive CamelCase with `Pattern` suffix (e.g.,
  `CreateReportPattern`, `AcceptInviteToEmbargoOnCasePattern`)

---

## Semantic Extraction — Pattern Ordering Rules

`SEMANTIC_REGISTRY` in `vultron/semantic_registry/` is **order-sensitive**.
Specific patterns MUST appear before more general ones. A pattern placed
after a more general match will never be reached.

- `ActivityPattern` instances are defined in `vultron/wire/as2/extractor.py`
  and imported into the domain sub-modules under `vultron/semantic_registry/`
- Always `rehydrate()` on incoming activities before pattern matching
- Add new `ActivityPattern` objects named `<TypeName>Pattern`
- Test every new pattern in `test/test_semantic_activity_patterns.py`

See `notes/activitystreams-semantics.md` for the full extractor design.

---

## Constructing Outbound Activities

All outbound Vultron activities MUST be constructed via the factory
functions in `vultron.wire.as2.factories`. Code outside
`vultron/wire/as2/vocab/activities/` and `vultron/wire/as2/factories/`
MUST NOT import internal activity subclasses (e.g.,
`RmCreateReportActivity`) directly. Use the corresponding factory function
instead (e.g., `rm_create_report_activity()`). This boundary is enforced
by `test/architecture/test_activity_factory_imports.py`.

---

## Key Files Map — wire layer

- **Patterns**: `vultron/wire/as2/extractor.py` — `ActivityPattern` class
  and `*Pattern` instance definitions
- **Semantic Registry**: `vultron/semantic_registry/` — domain-split package;
  `SEMANTIC_REGISTRY` (ordered list), `find_matching_semantics()`,
  `use_case_map()`
- **Vocab Examples**: `vultron/wire/as2/vocab/examples/` — reference for
  message semantics and test fixtures
- **Factories**: `vultron/wire/as2/factories/` — canonical constructors for
  all outbound activities

---

## Common Pitfalls — wire layer

**`SEMANTIC_REGISTRY` ordering errors fail silently — `_validate_registry_order()` required** —
see [notes/semantic-registry.md](../../../notes/semantic-registry.md)

A misplaced pattern (less-specific before more-specific within the same
`activity_` group) causes the wrong use case to execute with no error signal.
`_validate_registry_order()` raises `RegistryOrderError` at import time to
make this impossible to miss. Until that guard lands, run
`test/test_semantic_activity_patterns.py` immediately after editing the
registry.

See [notes/activitystreams-semantics.md](../../../notes/activitystreams-semantics.md)
for:

- Pattern Matching with ActivityStreams
- `VulnerabilityCase.case_activity` Cannot Store Typed Activities
- Accept/Reject `object` Field Must Use an Inline Typed Activity Object
- Pydantic Union Serialization Silently Returns `None` for `active_embargo`
- ActivityStreams as Wire Format, Not Domain Model
- Preserve Subclass Identity in ActivityStreams Decorators
- Dead-Letter vs. No-Pattern: Two Distinct UNKNOWN Failure Modes
- Accept.object\_ Must Be the Invite Activity, Not the Case Object
- Transitive Activity `object_` Contract at Base Type
- Base-Typed Serialization Drops Subtype Fields: Use `serialize_as_any=True`
- Invite Response Parsing Requires Recursive Rehydration
- Bootstrap Activities Must Embed Nested Objects Inline, Not as URI Strings
- Activity `name` Field Must Not Use `repr()` or `str()`
