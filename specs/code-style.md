# Code Style Specifications

## Overview

Defines code formatting and import organization standards for Python code.

**Source**: .pre-commit-config.yaml, copilot-instructions.md, ADR-0006  
**Note**: Applies to all Python source files and documentation code blocks

---

## Code Formatting

- `CS-01-001` Code MUST follow PEP 8 style guidelines
  - **Implementation**: Black formatter MUST be used for consistency
  - **Settings**: Default Black settings (88 character line length, etc.)
- `CS-01-002` Formatting checks MUST be included in CI/CD pipeline
  - Builds MUST fail if code does not conform to style guidelines
- `CS-01-003` Code formatting MUST be enforced
  - **Implementation**: Pre-commit hooks AND CI pipeline checks
  - `black`, `flake8`, `mypy`, and `pyright` MUST all pass cleanly before
    code is staged for commit
  - CI pipeline runs each linter as a separate parallel job; the build job
    proceeds only if all four pass (see `.github/workflows/python-app.yml`)
- `CS-01-006` Static type checking MUST be enforced in CI
  - Both `mypy` and `pyright` MUST pass with zero errors on all commits to
    `main` and on every pull request targeting `main`
  - **Rationale**: The codebase is known-clean; maintaining zero-warning
    status is required to preserve that baseline

## Docstring Standards

- `CS-01-004` Functions and methods SHOULD have docstrings following PEP 257
  conventions
  - Public APIs MUST have docstrings
  - Internal utilities MAY use brief one-line docstrings when purpose is clear
    from name
- `CS-01-005` Docstrings SHOULD follow Google style for structured sections
  - Include `Args`, `Returns`, `Raises` sections when informative
  - Omit empty sections for brevity
  
**Examples**:

```python
# Public API - comprehensive docstring
class ValidateReportReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: ValidateReportReceivedEvent
    ) -> None:
        """Validate vulnerability report and create case on acceptance.

        Args:
            dl: DataLayer instance for persistence operations
            request: Domain event carrying the validation activity

        Raises:
            VultronApiError: If report validation fails
            DataLayerError: If case creation fails

        Side Effects:
            - Updates report status to VALID or INVALID
            - Creates VulnerabilityCase on validation success
            - Adds CreateCase activity to actor outbox
        """
        self._dl = dl
        self._request = request

# Simple utility - brief docstring
def extract_id_segment(url: str) -> str:
    """Extract last path segment from URL for blackboard key."""
    return url.split('/')[-1]
```

- Use type hints for function signatures and variable annotations where
  appropriate
- Use descriptive variable and function names for readability

## Import Organization

- `CS-02-001` Imports SHOULD be organized in three groups: standard library, third-party libraries, local application
  - Each group separated by a single blank line
  - Within each group, imports sorted alphabetically
- `CS-02-002` Import statements SHOULD be placed at the top of the file after module comments or docstrings
  - In test modules, imports MUST NOT be placed inside test functions; all
    imports belong at module level. Placing imports inside test functions makes
    test discovery harder, obscures dependencies, and complicates refactoring.
- `CS-02-003` Multi-line import statements SHOULD use parentheses for readability

## Import Practices

- `CS-03-001` Wildcard imports (e.g., `from module import *`) MUST NOT be used
- `CS-03-002` Unused imports MUST be removed
- `CS-03-003` (MUST) When importing more than 10 items from a module, import the module itself instead
  - Access attributes as `module.attribute` for maintainability
  - **Rationale**: Reduces line noise and makes module boundaries clearer
- `CS-03-004` (SHOULD) In test modules, avoid multiple imports from the module under test; consider importing the module and using attribute access for clarity.
  - Shorthand aliases are acceptable in test modules where the context is clear (e.g., `import my_module as mm` in `test_my_module.py`)

## Circular Import Prevention

- `CS-05-001` Core modules SHALL NOT import from application layer modules
  - Core modules: `vultron/core/`, `vultron/wire/`
  - Application layer: `vultron/adapters/`
  - Note: `semantic_map.py`, `semantic_handler_map.py`, and `activity_patterns.py`
    no longer exist as top-level modules; their contents were relocated to
    `vultron/wire/as2/extractor.py` and `vultron/core/use_cases/use_case_map.py`
    as part of the hexagonal architecture refactoring (ARCH-CLEANUP-1)
- `CS-05-002` (SHOULD) When circular dependencies cannot be resolved by reorganization,
  use lazy initialization patterns as a **last resort**
  - Prefer module-level imports; local imports are a code smell indicating a
    circular dependency that SHOULD be refactored
  - Import inside functions only when refactoring is not possible or practical
  - When encountering existing local imports, attempt to refactor them to
    module-level before accepting them as-is
  - Use caching to avoid repeated initialization overhead
- `CS-05-003` Shared types and errors SHALL be placed in neutral modules
  - Example: `types.py` for shared type definitions, `dispatcher_errors.py` for dispatcher errors
- `CS-05-004` (MUST) Before adding imports between modules, trace the import chain to prevent cycles

**Verification**: Run `python -c "import vultron.MODULE_NAME"` to detect circular imports early

- `CS-04-001` Relative imports MAY be used for local application imports when appropriate
- `CS-04-002` Module imports MAY use aliases for clarity or to avoid naming conflicts
  - Aliases SHOULD be descriptive and widely recognized (e.g., `import numpy as np`)

## Module Size

- `CS-06-001` (SHOULD) Prefer modules that are < ~400 lines; split large modules by
  responsibility and avoid single-file catchalls
  - E.g., separate handlers registry, handler implementations, and handler
    utilities into distinct modules

## `as_` Field Prefix Policy

- `CS-07-001` (MUST NOT) use the `as_` prefix on Pydantic **field names**
  anywhere in the codebase. Class names (e.g., `as_Activity`, `as_Object`)
  retain the `as_` prefix as an ActivityStreams provenance marker.
- `CS-07-002` (MUST) For fields whose plain name collides with a Python builtin or
  reserved word (e.g., `object`, `type`, `id`, `context`), use a trailing
  underscore: `object_`, `type_`, `id_`, `context_`
  - Define a Pydantic field alias so that serialized JSON uses the clean
    name without the trailing underscore:

    ```python
    object_: str = Field(alias="object")
    ```

  - **Rationale**: Trailing underscore + alias is the idiomatic Python
    pattern (PEP 8) for builtin/reserved-word field names. It keeps models
    readable and decoupled from AS2 naming conventions across all layers.
- `CS-07-003` (MUST) Do not introduce new `as_`-prefixed field names anywhere.
  The migration of existing `as_`-prefixed field names was completed in
  NAMING-1 (2026-03-30). All wire-layer and core-layer field names now use
  the trailing-underscore convention where needed. Class names retain `as_`.

## Optional Field Non-Emptiness

- `CS-08-001` Optional string fields MUST NOT contain empty strings when
  present; the invariant is "if present, then non-empty"
  - The converse also applies: "if empty, then not present" — Pydantic
    validators SHOULD reject empty strings in fields that are declared
    `Optional[str]` or `str | None`
  - This pattern MUST be carried through to JSON Schemas derived from
    Pydantic models (e.g., via `minLength: 1` on string properties that
    are not required)
  - **Rationale**: Distinguishes "not provided" from "provided but blank",
    preventing ambiguous database states and simplifying downstream
    validation logic
- `CS-08-002` Non-empty string validation SHOULD be consolidated into a
  shared type alias rather than duplicated per-field validators
  - Define a `NonEmptyString` type (e.g., `Annotated[str, Field(min_length=1)]`)
    in a shared base module (e.g., `vultron/wire/as2/vocab/base/`)
  - For nullable fields that follow CS-08-001, use the inline form
    `NonEmptyString | None` rather than a named alias
  - Replace per-field `@field_validator` stubs that only check `if not v` or
    `if not v.strip()` with the shared type
  - **Rationale**: Eliminates boilerplate across many object models; makes the
    empty-string invariant visible in the field type signature rather than
    buried in a validator; aligns with Python/Pydantic idioms for reusable
    constraints
  - CS-08-002 refines CS-08-001

## Code Reuse

- `CS-09-001` New code SHOULD NOT duplicate logic already present elsewhere;
  prefer extracting shared logic into reusable helpers, base classes, or type
  aliases
  - Before creating a new function, class, or Pydantic model, check whether
    an existing one can be reused or extended
  - When a pattern repeats across three or more call sites, extract it into a
    shared helper
  - **Rationale**: Duplication inflates maintenance cost and allows bug fixes
    to be applied inconsistently
- `CS-09-002` Pydantic request and response models for API endpoints SHOULD be
  reused or inherited rather than duplicated
  - If two request models are structurally identical, define one and alias or
    inherit the other
  - If a new request model adds one field to an existing model, subclass the
    existing model
  - **Rationale**: Duplicated models diverge silently over time; a hierarchy
    makes the relationship explicit and reduces boilerplate

## Port and Adapter Data Exchange

- `CS-10-001` Data passed across port/adapter boundaries MUST use Pydantic
  `BaseModel`-derived classes rather than plain `dict`s
  - When a type is shared between a driving adapter and a driven adapter,
    define a shared base model in `vultron/core/models/` that both sides
    can import or extend
  - Adapters may add adapter-specific fields by subclassing the shared model
  - **Rationale**: `dict`s discard type information at the boundary, suppress
    validation, and make interfaces ambiguous. Pydantic models preserve
    validation, IDE support, and documentation at every layer crossing.

## Domain Event and Wire Activity Naming

- `CS-10-002` Wire-level ActivityStreams payload classes SHOULD carry the
  `Activity` suffix; domain event classes SHOULD carry the `Event` suffix
  - **Wire layer** (`vultron/wire/as2/vocab/activities/`): classes named
    `FooActivity` (e.g., `ReportSubmitActivity`) represent structured payloads
    recognized by the semantic extractor
  - **Domain layer** (`vultron/core/models/events/`): classes named `FooEvent`
    (e.g., `ReportSubmittedEvent`) represent typed domain events consumed by
    handlers and use cases
  - Domain events that originate from received wire messages SHOULD use the
    `FooReceivedEvent` subtype suffix (e.g., `ReportSubmittedReceivedEvent`)
  - Domain events that originate from local actor-initiated triggers SHOULD
    use the `FooTriggerEvent` subtype suffix (e.g., `ValidateReportTriggerEvent`)
  - **Rationale**: Distinguishes wire representation from domain intent,
    prevents accidental coupling between layers, and makes the translation
    point explicit. See `notes/domain-model-separation.md` for the full
    design rationale.

## Type Annotations

- `CS-11-001` Code MUST NOT use `Any` in type hints when the type can be
  determined
  - If a type is complex, define a Pydantic model or a type alias rather than
    using `Any`
  - Use `Any` only as a last resort when the type is genuinely unknown or
    when interfacing with untyped third-party code that cannot be typed otherwise
  - When you find yourself reaching for `Any`, treat it as a signal to
    refactor: the type structure may need to be made more explicit
  - **Rationale**: `Any` defeats static type checking, obscures API
    contracts, and hides bugs at the boundary between typed and untyped code

## Domain Model Naming

- `CS-12-001` Core domain model class names SHOULD reflect the domain concept
  they represent, not a parallel to a wire-format class name
  - Instead of `VultronOffer` (a parallel to the AS2 `Offer` activity),
    use a name that reflects the use case:
    `CaseTransferOffer`, `ReportSubmissionOffer`, `EmbargoInvitation`, etc.
  - Instead of `VultronEvent`, use a name that reflects the specific
    semantic: `ReportSubmittedEvent`, `CaseCreatedEvent`, etc.
  - **Rationale**: Generic wire-mirroring names obscure what an object
    actually represents in the CVD domain. Domain-centric names make the
    code self-documenting and reduce reliance on comments to explain intent.
  - **Scope**: Applies to new classes in `vultron/core/` and to existing
    classes when they are refactored; do not rename existing classes
    incidentally while working on unrelated changes

## Datetime and Timezone Conventions

- `CS-13-001` All datetime values produced by the application MUST be
  timezone-aware and MUST use UTC
  - Naive `datetime` objects (without timezone info) MUST NOT be stored in
    domain models, written to the DataLayer, or included in wire output
  - **Rationale**: Naive datetimes are ambiguous in a distributed system
    where actors may run in different timezones; UTC eliminates this
    ambiguity
- `CS-13-002` All datetime values MUST be created via the `now_utc()` helper
  in `vultron.wire.as2.vocab.base.dt_utils`
  - Direct calls to `datetime.now()` (without `tz=timezone.utc`) or
    `datetime.utcnow()` (which returns a naive UTC datetime) MUST NOT appear
    in new code
  - `now_utc()` returns `datetime.now(timezone.utc).replace(microsecond=0)`;
    using it everywhere ensures uniform precision and timezone handling
- `CS-13-003` All datetime values SHOULD be stored at second precision
  (microseconds set to zero)
  - Sub-second precision is not required by the Vultron protocol for most
    use cases; stripping microseconds reduces storage noise and ensures
    identical objects produce identical serialized representations
  - `now_utc()` enforces this by calling `.replace(microsecond=0)`
  - Where sub-second precision is needed (e.g., for high-frequency events
    or integration with external systems that supply microsecond-resolution
    timestamps), microsecond precision MAY be retained
- `CS-13-004` Embargo deadline datetimes MUST be computed using the
  `days_from_now_utc(n)` helper rather than inline arithmetic
  - `days_from_now_utc(n)` returns `now_utc() + timedelta(days=n)`, which
    inherits the UTC and second-precision guarantees of `now_utc()`
- `CS-13-005` Wire-format datetime fields MUST serialize to RFC 3339 / ISO 8601
  format with explicit UTC offset (`Z` or `+00:00`)
  - Acceptable forms: `YYYY-MM-DDTHH:MM:SSZ` or `YYYY-MM-DDTHH:MM:SS+00:00`
  - See RFC 3339 for the definitive format specification
  - Pydantic serializes timezone-aware `datetime` objects to ISO 8601 by
    default; no custom serializer is needed as long as CS-13-001 is followed

## Wire Model Configuration

- `CS-14-001` (MUST) Wire-layer Pydantic models (classes in
  `vultron/wire/as2/vocab/`) MUST inherit `model_config` from `as_Base`,
  which sets `alias_generator=to_camel`, `validate_by_name=True`, and
  `validate_by_alias=True`
  - These settings ensure that AS2 JSON with camelCase keys (e.g.,
    `"inReplyTo"`) can be deserialized into Python models with snake_case
    fields (e.g., `in_reply_to`) without explicit per-field alias
    declarations
  - Subclasses that override `model_config` MUST extend the parent config
    to preserve these settings; see `specs/vocabulary-model.md` VM-02-001
- `CS-14-002` (MUST) Core/domain-layer Pydantic models (classes in
  `vultron/core/models/`) MUST set `populate_by_name=True` in their
  `model_config`
  - This allows field access using both the Python field name and the
    alias, which is necessary for DataLayer round-tripping and use-case code
    that constructs models using keyword arguments matching Python field names
  - Domain models MUST NOT inherit the wire layer's `alias_generator=to_camel`
    unless they are also intended for direct wire serialization
- `CS-14-003` Domain event subclasses MUST narrow the `semantic_type` field
  to a `Literal[MessageSemantics.FOO]` type with the corresponding default
  value
  - This enables Pydantic discriminated-union deserialization and makes the
    expected semantic type explicit in the class definition
  - Example: `semantic_type: Literal[MessageSemantics.CREATE_CASE] = MessageSemantics.CREATE_CASE`
  - CS-14-003 refines CS-10-002

## Use Case Naming

- `CS-12-002` Use case class names SHOULD carry a suffix that reflects their
  origin (received message vs. local trigger):
  - **Handler use cases** (processing messages received from another party, in
    `core/use_cases/<domain>.py`) SHOULD carry the `Received` suffix:
    `CreateReportReceivedUseCase`, `AcceptInviteActorToCaseReceivedUseCase`, etc.
  - **Trigger use cases** (executing actor-initiated behaviors, in
    `core/use_cases/triggers/`) SHOULD carry the `Svc` prefix:
    `SvcEngageCaseUseCase`, `SvcProposeEmbargoUseCase`, etc.
  - The `USE_CASE_MAP` in `core/use_cases/use_case_map.py` MUST be updated in
    the same commit as any rename
  - **Rationale**: Distinguishes messages received from external parties from
    actions the local actor has decided to take. This distinction is fundamental
    to the Vultron protocol model (see `notes/activitystreams-semantics.md`)
    and prevents accidentally treating incoming messages as local commands.
  - **See also**: TECHDEBT-21 for the rename task; CS-10-002 for the parallel
    `FooReceivedEvent` / `FooTriggerEvent` domain event convention
