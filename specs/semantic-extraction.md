# Semantic Extraction Specification

## Overview

The inbox handler extracts semantic meaning from ActivityStreams activities by matching activity type and object type patterns. This semantic type determines which handler function processes the activity.

**Total**: 6 requirements  
**Source**: Protocol design, message routing architecture

---

## Pattern Matching (MUST)

- `SE-001` The system MUST match activities using activity type and object type patterns
  - Support nested object type matching (e.g., Accept of Offer of VulnerabilityReport)
  - Evaluate patterns in order of specificity (most specific first)

## Semantic Type Assignment (MUST)

- `SE-002` The system MUST assign MessageSemantics enum value via `find_matching_semantics()`
- `SE-003` The function MUST return the first matching semantic type

## Pattern Registry (MUST)

- `SE-004` SEMANTIC_ACTIVITY_PATTERNS MUST contain patterns for all supported operations
- `SE-005` Pattern registry MUST be ordered from most specific to least specific

## Unrecognized Activity Handling (MUST)

- `SE-006` The system MUST log unrecognized activities at WARNING level
- `SE-007` The system MUST raise VultronApiHandlerMissingSemanticError for unmatched activities

## Pattern Validation (MUST)

- `SE-008` All patterns MUST have corresponding MessageSemantics enum value
- `SE-009` All patterns MUST have corresponding handler function in SEMANTIC_HANDLER_MAP
- `SE-010` All patterns MUST have unit test coverage

## Verification

### SE-001, SE-002, SE-003 Verification
- Unit test: Simple pattern (Create VulnerabilityCase) → MessageSemantics.CREATE_CASE
- Unit test: Nested pattern (Accept Offer VulnerabilityReport) → MessageSemantics.VALIDATE_REPORT
- Unit test: Most specific pattern matches first (multiple possible matches)

### SE-004, SE-005 Verification
- Unit test: Verify all MessageSemantics values except UNKNOWN have pattern
- Unit test: Verify pattern ordering (specific before general)

### SE-006, SE-007 Verification
- Unit test: Unrecognized activity → VultronApiHandlerMissingSemanticError raised
- Unit test: Verify WARNING log entry for unrecognized activity
- Unit test: Error message includes activity type and object type

### SE-008, SE-009, SE-010 Verification
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
