# Semantic Extraction Specification

## Context

The inbox handler must extract semantic meaning from ActivityStreams activities by matching activity type and object type patterns. This semantic type determines which handler function processes the activity.

## Requirements

### SE-1: Pattern Matching Algorithm - Match on activity type and object type with nested support
### SE-2: Semantic Type Assignment - Assign MessageSemantics enum value via find_matching_semantics()
### SE-3: Pattern Registry Completeness - Contains patterns for all supported operations
### SE-4: Pattern Specificity Ordering - Order from most specific to least specific
### SE-5: Unrecognized Activity Handling - Log at WARNING and raise VultronApiHandlerMissingSemanticError
### SE-6: Pattern Validation - All patterns have corresponding enum, handler, and tests

## Verification

See full specification for detailed verification criteria.

## Related

- Implementation: `vultron/semantic_map.py`
- Implementation: `vultron/activity_patterns.py`
- Implementation: `vultron/behavior_dispatcher.py`
- Implementation: `vultron/enums.py`
- Tests: `test/test_semantic_activity_patterns.py`
- Tests: `test/test_semantic_handler_map.py`
- Related Spec: [dispatch-routing.md](dispatch-routing.md)
- Related Spec: [handler-protocol.md](handler-protocol.md)

