# Vocabulary Model Specification

## Overview

Requirements governing how ActivityStreams 2.0 vocabulary types are defined,
registered, configured, and deserialized in the Vultron wire layer.
The vocabulary model is the foundation of the inbound pipeline: every
activity that enters the system must be deserialized into a known vocabulary
type before semantic extraction can assign it a domain meaning.

**Source**: `vultron/wire/as2/vocab/base/`, `vultron/wire/as2/vocab/`,
`vultron/wire/as2/rehydration.py`, `notes/activitystreams-semantics.md`,
`notes/architecture-ports-and-adapters.md`

**Cross-references**: `architecture.md` ARCH-03-001 (sole mapping point),
`semantic-extraction.md` SE-01-002 (rehydration before extraction),
`code-style.md` CS-07-001 (as_ prefix policy),
`object-ids.md` OID-01-001 (full-URI IDs)

---

## Vocabulary Registration

- `VM-01-001` (MUST) Every concrete wire-layer AS2 class (object, activity, or
  link) MUST be registered in the shared `VOCABULARY` registry automatically
  at class-definition time
  - Registration MUST occur via `as_Base.__init_subclass__`, which fires once
    when the class body is executed (i.e., at module import time)
  - A class is treated as concrete — and therefore registered — when its
    `type_` field annotation is `Literal[str]`; abstract or intermediate base
    classes that leave `type_` typed as `str | None` are skipped
  - The registration key is the `Literal` value (e.g., `"Create"`,
    `"VulnerabilityCase"`), which MUST equal the AS2 wire type name
  - Unregistered types cannot be deserialized from storage or rehydrated from
    URI references; any unregistered wire type is a runtime defect
    - VM-01-001 is-implemented-by `as_Base.__init_subclass__` in
      `vultron/wire/as2/vocab/base/base.py`
- `VM-01-002` (MUST) The `VOCABULARY` singleton MUST be the sole authoritative
  source for type lookup during dynamic deserialization
  - `find_in_vocabulary()` MUST be used wherever a type must be resolved by
    name (e.g., in `record_to_object()`, `rehydrate()`, parser utilities)
  - Direct imports of concrete vocab classes inside deserialization paths
    MUST NOT bypass `find_in_vocabulary()`; such direct imports couple the
    deserializer to specific types and prevent vocabulary extension
  - `find_in_vocabulary()` MUST raise `KeyError` when the requested type name
    is not in the registry (fail-fast; see VM-06-005)
- `VM-01-003` (MUST) New vocabulary types MUST be importable at startup without
  explicit registration calls in application code
  - Registration MUST happen as a side effect of the class definition via
    `__init_subclass__`, so that any module importing the class also registers
    it automatically
- `VM-01-004` (MUST) The `VOCABULARY` registry MUST be a flat
  `dict[str, type[as_Base]]` keyed by AS2 type name
  - AS2 vs. Vultron provenance is expressed as a `_vocab_ns: ClassVar[VocabNamespace]`
    attribute on each class (see VM-01-006), not as a registry key dimension
  - This design avoids forcing callers to know the provenance of a type when
    all they have is the wire `"type"` string
- `VM-01-005` (MUST) The `vocab/objects/__init__.py` and
  `vocab/activities/__init__.py` files MUST use `pkgutil.iter_modules` and
  `importlib.import_module` to dynamically import all sibling modules at
  package import time
  - This provides a startup guarantee that all vocabulary classes are defined
    and registered before any deserialization occurs, independent of which
    application code paths happen to import specific vocab classes
  - VM-01-005 refines VM-01-001
- `VM-01-006` (MUST) A `VocabNamespace` enum (values: `AS`, `VULTRON`) MUST
  be defined in `vultron/wire/as2/vocab/base/enums.py` and used to annotate
  the provenance of each vocabulary class
  - `as_Base` MUST declare `_vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.AS`
  - `VultronObject` MUST override this to `_vocab_ns = VocabNamespace.VULTRON`
  - All Vultron-specific object subclasses inherit `VocabNamespace.VULTRON` from
    `VultronObject` without additional annotation; AS2 base types inherit
    `VocabNamespace.AS` from `as_Base`

## Base Model Configuration

- `VM-02-001` All wire-layer AS2 Pydantic models MUST inherit `model_config`
  from `as_Base` (or an intermediate class that inherits from `as_Base`),
  which provides:
  - `alias_generator=to_camel`: field names are serialized/deserialized
    using camelCase aliases (e.g., `as_type` → `"type"`,
    `published_at` → `"publishedAt"`)
  - `validate_by_name=True`: accepts Python field names during validation,
    in addition to aliases
  - `validate_by_alias=True`: accepts camelCase aliases during validation
  - Any subclass that overrides `model_config` MUST extend the parent
    config rather than replace it
- `VM-02-002` The `@context` field (`as_context`) MUST use explicit
  `validation_alias="@context"` and `serialization_alias="@context"` because
  `@` is not a valid Python identifier character and cannot be handled by the
  camelCase alias generator
  - VM-02-002 refines VM-02-001
- `VM-02-003` Wire-layer models MUST provide `to_json()`, `to_dict()`, and
  `from_json()` convenience methods that exclude `None` values and serialize
  using aliases by default
  - These are inherited from `as_Base`; subclasses MUST NOT override them in
    ways that change the `exclude_none=True` or `by_alias=True` defaults,
    as doing so would produce non-standard AS2 output

## Type Auto-Inference

- `VM-03-001` The `as_type` field on every concrete wire-layer class MUST be
  set automatically at construction time if not supplied by the caller
  - `as_Base` provides a `model_validator(mode="after")` that sets
    `as_type` to `self.__class__.__name__.lstrip("as_")` when `as_type is None`
  - This validator MUST NOT be removed or overridden in subclasses
- `VM-03-002` Concrete subclasses SHOULD narrow the `as_type` field to a
  `Literal[...]` type matching the wire type name they represent
  - This enables Pydantic discriminated-union deserialization and makes the
    expected wire type explicit in the class definition
  - Example: `as_type: Literal["Create"] = "Create"` in a `CreateActivity`
    subclass
  - VM-03-002 refines VM-03-001
- `VM-03-003` `as_type` values MUST NOT start with `"as_"` in serialized
  wire output
  - The `as_` prefix is a Python naming convention for classes to signal
    ActivityStreams provenance; it MUST NOT appear in the serialized `type`
    field because AS2 type names do not carry this prefix
  - VM-03-003 constrains VM-03-001

## ID Generation

- `VM-04-001` All wire-layer objects MUST have a globally unique `as_id`
  field set at construction time by `generate_new_id()` if not supplied
  - The default form is `urn:uuid:{uuid4}` — a valid AS2 identifier that
    requires no HTTP server configuration
  - Callers that create objects with a known base URL SHOULD pass a prefix
    to `generate_new_id(prefix)` to produce `https://…/{uuid}` style IDs
  - VM-04-001 implements OID-01-001

## Vocabulary Extension

- `VM-05-001` (MUST) When adding a new Vultron-specific object type, the new class
  MUST:
  1. Inherit from `VultronObject` (or an appropriate AS2 base such as
     `as_Object`, `as_Activity`, etc.)
  2. Define `type_` as a `Literal[str]` field matching the wire type name
     (registration via `__init_subclass__` fires automatically)
  3. Be placed in the vocabulary subpackage that matches its category
     (`vocab/objects/`, `vocab/activities/`)
  4. Be reachable via the dynamic discovery in the subpackage `__init__.py`
     (i.e., exist as a `.py` file in the package directory)
- `VM-05-002` (MUST) Adding a new vocabulary type that represents a domain concept
  MUST be accompanied by:
  - A `MessageSemantics` enum value (see `architecture.md` ARCH-02-001)
  - An `ActivityPattern` in `extractor.py` (see `semantic-extraction.md`
    SE-03-001)
  - A handler use-case class registered in `USE_CASE_MAP`
  - Tests for pattern matching and dispatch

## Rehydration

- `VM-06-001` (MUST) Before any wire-layer activity is passed to semantic extraction,
  callers MUST attempt to rehydrate all nested URI string references into
  fully typed objects via `rehydrate(obj, dl)`
  - VM-06-001 refines SE-01-002 (semantic-extraction.md)
- `VM-06-002` `rehydrate()` MUST receive the active `DataLayer` instance via
  the `dl` parameter
  - `rehydrate()` MUST NOT be called without a DataLayer; calling with a
    `None` DataLayer is a programming error and MUST raise immediately
  - This is required because URI string references must be resolved from
    persistent storage, not from in-memory state
- `VM-06-003` Rehydration MUST be recursive: if a rehydrated object itself
  contains URI string references in its nested fields, those MUST also be
  rehydrated up to `MAX_REHYDRATION_DEPTH` levels
  - Exceeding `MAX_REHYDRATION_DEPTH` MUST raise `RecursionError` to
    prevent infinite loops on circular reference graphs
- `VM-06-004` (MUST) If a URI string reference cannot be resolved (object not in
  DataLayer), rehydration MUST:
  - Log a warning identifying the unresolvable URI
  - Raise `ValueError` to indicate that the object cannot be found
  - The caller (semantic extraction pipeline) then returns
    `MessageSemantics.UNKNOWN`
  - VM-06-004 implements SE-01-003 (semantic-extraction.md)
- `VM-06-005` (MUST) If a rehydrated object's `as_type` is not found in the
  vocabulary registry, rehydration MUST raise `KeyError` or `ValueError`
  rather than returning a partially constructed object
  - An unknown type in the rehydration path indicates a vocabulary
    registration gap that MUST be corrected before deployment

## Serialization Rules

- `VM-07-001` Serialized wire-layer objects MUST exclude `None` fields and
  MUST exclude empty string fields
  - `to_json()` and `to_dict()` MUST pass `exclude_none=True` to
    `model_dump_json()` / `model_dump()` so that optional absent fields
    are omitted from wire output (AS2 convention)
  - Empty strings MUST also be excluded because many JSON processing
    mechanisms handle empty strings poorly, and their presence adds payload
    noise without contributing semantics
- `VM-07-002` Serialized wire-layer objects MUST use camelCase field aliases
  in output, not Python snake_case field names
  - `to_json()` MUST pass `by_alias=True`
  - Serialization that produces `as_type` or `as_id` keys in JSON output
    is incorrect; the wire format uses `"type"` and `"id"` respectively
- `VM-07-003` `object_to_record()` MUST NOT be called on an object whose
  `as_type` starts with `"as_"`
  - Objects stored in the DataLayer have their `type_` field set to the AS2
    type name (without the `as_` prefix); a value starting with `"as_"` would
    break `find_in_vocabulary()` lookup during `record_to_object()`

## Static Object Integrity

- `VM-08-001` (SHOULD) Objects intended to be static once created (e.g., vocabulary
  registry entries, canonical example objects) SHOULD use immutable
  (frozen) configuration so that any attempt to modify them at runtime
  raises an exception
  - Pydantic's `model_config = ConfigDict(frozen=True)` SHOULD be used for
    such classes
  - Immutability ensures that runtime integrity violations are caught
    immediately rather than silently corrupting shared state

## Unknown Message Handling

- `VM-09-001` (MAY) Messages that cannot be parsed or whose semantics are unknown
  MAY still be forwarded to the case event log to create an entry for
  human or agent review
  - This provides an opening for manual override: a user or advanced agent
    can inspect the raw message and manually translate its content into the
    necessary state changes
  - The case event log entry for an unknown message MUST record at minimum
    the raw message identifier and the reason it could not be parsed

## Verification

### VM-01-001 through VM-01-006 Verification

- Unit test: After importing `vocab/objects` and `vocab/activities`, all
  concrete classes (those with `Literal` `type_` annotations) appear in
  `VOCABULARY`; abstract bases (`as_Object`, `VultronObject`, `as_Activity`,
  `as_Actor`) do not
- Unit test: `find_in_vocabulary("VulnerabilityCase")` returns the correct
  class after importing the objects vocabulary subpackage
- Unit test: `find_in_vocabulary("UnknownType")` raises `KeyError`
- Unit test: `record_to_object()` correctly reconstructs objects whose type
  is registered; raises `KeyError` for unregistered types
- Unit test: Defining a new concrete `as_Base` subclass with
  `type_: Literal["TestType"]` results in `"TestType"` appearing in
  `VOCABULARY` without any decorator
- Unit test: Every `.py` module in `vocab/objects/` and `vocab/activities/`
  contributes at least one class to `VOCABULARY` after the package is imported
  (registration completeness test)

### VM-02-001, VM-02-002, VM-02-003 Verification

- Unit test: Deserializing `{"type": "Create", "id": "urn:uuid:…"}` produces
  a `as_Create` object; `"type"` field accepted despite being an alias
- Unit test: `as_Base` subclass field names with underscore accept both
  camelCase JSON key and snake_case Python attribute name
- Unit test: `to_json()` output contains `"@context"`, not `"asContext"`

### VM-03-001, VM-03-003 Verification

- Unit test: Constructing any concrete vocab class without supplying `as_type`
  produces a correctly populated `as_type` field matching the class name
  (minus `as_` prefix)
- Unit test: No concrete vocab class serializes `as_type` as a value starting
  with `"as_"`

### VM-06-001 through VM-06-005 Verification

- Unit test: `rehydrate(str_id, dl)` resolves the ID via `dl.read()` and
  returns the correct typed object
- Unit test: Rehydration beyond `MAX_REHYDRATION_DEPTH` raises `RecursionError`
- Unit test: Unresolvable URI logs a warning and raises `ValueError`

### VM-07-001 through VM-07-003 Verification

- Unit test: `obj.to_dict()` contains no `None` values
- Unit test: `obj.to_json()` uses `"type"` and `"id"`, not `"as_type"` /
  `"as_id"` as JSON keys
- Unit test: `object_to_record(obj)` raises `ValueError` when `obj.as_type`
  starts with `"as_"`

## Related

- **Wire vocabulary**: `vultron/wire/as2/vocab/`
- **Registry**: `vultron/wire/as2/vocab/base/registry.py`
- **Base model**: `vultron/wire/as2/vocab/base/base.py`
- **Rehydration**: `vultron/wire/as2/rehydration.py`
- **Record helpers**: `vultron/adapters/driven/db_record.py`
- **Semantic extraction**: `specs/semantic-extraction.yaml`
- **Architecture**: `specs/architecture.yaml` (ARCH-03-001)
- **Object IDs**: `specs/object-ids.yaml` (OID-01-001)
- **Code style**: `specs/code-style.yaml` (CS-07-001)
