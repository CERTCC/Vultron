# Semantic Extraction Specification

## Overview

The inbox handler extracts semantic meaning from ActivityStreams activities by matching activity type and object type patterns. This semantic type determines which handler function processes the activity.

**Source**: Protocol design, message routing architecture

---

## Pattern Matching

- `SE-01-001` The system MUST match activities using activity type and object
  type patterns
  - Support nested object type matching (e.g., Accept of Offer of
    VulnerabilityReport)
  - Evaluate patterns in order of specificity (most specific first)
- `SE-01-002` The semantic extraction algorithm MUST handle both fully expanded
  objects and URI string references defensively
  - Pattern matching MUST NOT fail when activity fields contain URI strings
    rather than fully expanded objects
  - **Note**: Activities SHOULD be rehydrated before semantic extraction to
    ensure accurate pattern matching; see `notes/activitystreams-semantics.md`
- `SE-01-003` If rehydration fails for any nested object, the system MUST:
  - Log a warning identifying the failed URI
  - Return `MessageSemantics.UNKNOWN` from semantic extraction
  - Delegate to the unknown activity handler
- `SE-01-004` Pattern matching MUST support type/subclass matching semantics
  for actor/object classes
  - Subclass relationships MUST be considered when matching against actor or
    object type patterns (e.g., `as_Person` and `as_Organization` satisfy an
    `as_Actor` pattern)
  - Pattern matching MUST be robust to fields that are either fully expanded
    objects or URI string references
  - When a field is a URI string reference, the matching algorithm MUST NOT
    infer the object type from the string; rehydration MUST be attempted
    before type-based matching
  - If rehydration is not possible, the pattern MUST be treated as unmatched
    and a warning MUST be logged
  - SE-01-004 depends-on SE-01-002

## Semantic Type Assignment

- `SE-02-001` The system MUST assign MessageSemantics enum value via `find_matching_semantics()`
- `SE-02-002` The function MUST return the first matching semantic type
- `SE-02-003` The function MUST return MessageSemantics.UNKNOWN if no patterns match

## Pattern Registry

- `SE-03-001` SEMANTICS_ACTIVITY_PATTERNS MUST contain patterns for all supported MessageSemantics values except UNKNOWN
- `SE-03-002` Pattern registry MUST be ordered from most specific to least specific
- `SE-03-003` (MUST) Every `ActivityPattern` entry in `SEMANTICS_ACTIVITY_PATTERNS`
  MUST discriminate on at minimum both Activity type AND Object type
  - Patterns that match on Activity type alone (without an `object_type`
    constraint) are NOT permitted
  - **Rationale**: A pattern without an object-type constraint would match
    every activity of that verb type regardless of payload, causing
    misrouting when multiple semantics share an outer Activity type
  - For nested activity patterns (e.g., `Accept(Offer(VulnerabilityReport))`),
    the inner activity type and its object type MUST also be discriminated
    where multiple nested patterns share the same outer shape

## Unrecognized Activity Handling

- `SE-04-001` The system MUST log unrecognized activities at WARNING level
- `SE-04-002` The system MUST distinguish two causes of `MessageSemantics.UNKNOWN`:
  1. **No pattern match**: No registered `ActivityPattern` matched the activity
     structure → raise `VultronApiHandlerMissingSemanticError`
  2. **Unresolvable `object_`**: `object_` remains a bare string URI after
     rehydration (per VAM-01-009) → do NOT raise an error; instead log a
     WARNING, store the activity in a dead-letter record, and return silently
  - **Rationale**: An unresolvable `object_` URI is not a programming error;
    it is a data completeness issue that may resolve later. Treating it as a
    5xx error would cause unnecessary noise and fail legitimate protocol flows.
- `SE-04-003` (MUST) Dead-letter records for unresolvable-object_ activities
  MUST include: the full activity JSON, the unresolvable URI, the actor ID,
  and a timestamp. They MUST be stored in a DataLayer collection accessible
  for administrative review and retry.
- `SE-04-004` For any future synchronous processing path (non-background),
  UNKNOWN due to unresolvable `object_` MUST return HTTP 422 with an
  explanatory error body identifying the unresolvable URI

## Pattern Validation

- `SE-05-001` All patterns MUST have corresponding MessageSemantics enum value
- `SE-05-002` All patterns MUST have corresponding use-case class in USE_CASE_MAP
  - SE-05-002 derives-from DR-02-002
- `SE-05-003` All patterns MUST have unit test coverage

## Verification

### SE-01-001, SE-01-002, SE-01-003, SE-02-001, SE-02-002 Verification

- Unit test: Simple pattern (Create VulnerabilityCase) →
  MessageSemantics.CREATE_CASE
- Unit test: Nested pattern (Accept Offer VulnerabilityReport) →
  MessageSemantics.VALIDATE_REPORT
- Unit test: Most specific pattern matches first (multiple possible matches)
- Unit test: Pattern matching handles URI string references without raising exceptions
- Unit test: Rehydration failure returns MessageSemantics.UNKNOWN and logs WARNING

### SE-03-001, SE-03-002 Verification

- Unit test: Verify all MessageSemantics values except UNKNOWN have pattern
- Unit test: Verify pattern ordering (specific before general)

### SE-04-001, SE-04-002 Verification

- Unit test: Unrecognized activity → VultronApiHandlerMissingSemanticError raised
- Unit test: Verify WARNING log entry for unrecognized activity
- Unit test: Error message includes activity type and object type

### SE-05-001, SE-05-002, SE-05-003 Verification

- Unit test: All patterns in SEMANTICS_ACTIVITY_PATTERNS have enum entry
- Unit test: All patterns have corresponding use-case class in USE_CASE_MAP
- Code coverage: All patterns exercised by tests

## Related

- Implementation: `vultron/wire/as2/extractor.py` (patterns and
  `find_matching_semantics`; sole AS2→domain mapping point)
- Implementation: `vultron/core/dispatcher.py`
- Implementation: `vultron/wire/as2/rehydration.py` (object rehydration)
- Implementation: `vultron/adapters/driving/fastapi/inbox_handler.py` (rehydration before dispatch)
- Implementation: `vultron/core/models/events.py` (`MessageSemantics` enum)
- Tests: `test/test_semantic_activity_patterns.py`
- Tests: `test/test_semantic_handler_map.py`
- Related Spec: [dispatch-routing.md](dispatch-routing.md)
- Related Spec: [handler-protocol.md](handler-protocol.md)
