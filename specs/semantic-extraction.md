# Semantic Extraction Specification

## Overview

The inbox handler extracts semantic meaning from ActivityStreams activities by matching activity type and object type patterns. This semantic type determines which handler function processes the activity.

**Source**: Protocol design, message routing architecture

---

## Pattern Matching (MUST)

- `SE-01-001` The system MUST match activities using activity type and object type patterns
  - Support nested object type matching (e.g., Accept of Offer of VulnerabilityReport)
  - Evaluate patterns in order of specificity (most specific first)

## Semantic Type Assignment (MUST)

- `SE-02-001` The system MUST assign MessageSemantics enum value via `find_matching_semantics()`
- `SE-02-002` The function MUST return the first matching semantic type
- `SE-02-003` The function MUST return MessageSemantics.UNKNOWN if no patterns match

## Pattern Registry (MUST)

- `SE-03-001` SEMANTIC_ACTIVITY_PATTERNS MUST contain patterns for all supported MessageSemantics values except UNKNOWN
- `SE-03-002` Pattern registry MUST be ordered from most specific to least specific

## Unrecognized Activity Handling (MUST)

- `SE-04-001` The system MUST log unrecognized activities at WARNING level
- `SE-04-002` The system MUST raise VultronApiHandlerMissingSemanticError for unmatched activities

## Pattern Validation (MUST)

- `SE-05-001` All patterns MUST have corresponding MessageSemantics enum value
- `SE-05-002` All patterns MUST have corresponding handler function in SEMANTIC_HANDLER_MAP
- `SE-05-003` All patterns MUST have unit test coverage

## Verification

### SE-01-001, SE-02-001, SE-02-002 Verification
- Unit test: Simple pattern (Create VulnerabilityCase) → MessageSemantics.CREATE_CASE
- Unit test: Nested pattern (Accept Offer VulnerabilityReport) → MessageSemantics.VALIDATE_REPORT
- Unit test: Most specific pattern matches first (multiple possible matches)

### SE-03-001, SE-03-002 Verification
- Unit test: Verify all MessageSemantics values except UNKNOWN have pattern
- Unit test: Verify pattern ordering (specific before general)

### SE-04-001, SE-04-002 Verification
- Unit test: Unrecognized activity → VultronApiHandlerMissingSemanticError raised
- Unit test: Verify WARNING log entry for unrecognized activity
- Unit test: Error message includes activity type and object type

### SE-05-001, SE-05-002, SE-05-003 Verification
- Unit test: All patterns in SEMANTIC_ACTIVITY_PATTERNS have enum entry
- Unit test: All patterns have corresponding handler in SEMANTIC_HANDLER_MAP
- Code coverage: All patterns exercised by tests

## Related

- Implementation: `vultron/api/v2/backend/semantic_map.py`
- Implementation: `vultron/api/v2/backend/activity_patterns.py`
- Implementation: `vultron/api/v2/backend/behavior_dispatcher.py`
- Implementation: `vultron/enums.py`
- Tests: `test/api/v2/backend/test_semantic_activity_patterns.py`
- Tests: `test/api/v2/backend/test_semantic_handler_map.py`
- Related Spec: [dispatch-routing.md](dispatch-routing.md)
- Related Spec: [handler-protocol.md](handler-protocol.md)
