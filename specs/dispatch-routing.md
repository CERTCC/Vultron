# Dispatch Routing Specification

## Overview

After semantic extraction, the dispatcher routes `VultronEvent` domain objects
to the appropriate use-case class. The dispatcher may execute use cases
synchronously (DirectActivityDispatcher) or asynchronously (queue-based).

**Source**: Design documents, handler protocol requirements

---

## Dispatcher Protocol (MUST)

- `DR-01-001` All dispatcher implementations MUST implement ActivityDispatcher protocol
- `DR-01-002` Dispatchers MUST construct use-case instances with the complete
  `VultronEvent` and `DataLayer` before calling `execute()`, so that `execute()`
  takes no arguments
  - The use-case constructor is responsible for storing `dl` and `request`;
    `execute()` accesses them via `self._dl` and `self._request`
  - DR-01-002 constrains all use-case classes to the `UseCase[Req, Res]`
    protocol defined in `vultron/core/ports/use_case.py`
- `DR-01-003` Dispatchers MUST perform semantic type validation at dispatch time using the configured
  semantics-to-use-case mapping

## Handler Lookup (MUST)

- `DR-02-001` The system MUST look up use-case classes by semantic type using `USE_CASE_MAP`
- `DR-02-002` `USE_CASE_MAP` MUST contain entries for all MessageSemantics values

## Direct Dispatch Implementation (MUST)

- `DR-03-001` The DirectActivityDispatcher MUST execute handlers synchronously
- `DR-03-002` The DirectActivityDispatcher MUST catch and log handler exceptions at ERROR level
  - DR-03-002 depends-on SL-03-001
  - DR-03-002 depends-on EH-06-001
  - **Verification**: Logged exceptions include handler name, activity ID, and full error context

## Async Dispatch Implementation (SHOULD)

- `DR-04-001` An async dispatcher SHOULD queue activities for processing
- `DR-04-002` An async dispatcher SHOULD process activities in FIFO order

## Verification

### DR-01-001, DR-01-002, DR-01-003 Verification

- Unit test: Verify DirectActivityDispatcher implements ActivityDispatcher protocol
- Unit test: Verify dispatcher constructs use-case with `VultronEvent` and `DataLayer` before calling `execute()`
- Unit test: Verify `execute()` takes no arguments
- Unit test: Verify semantic type validation occurs at dispatch time

### DR-02-001, DR-02-002 Verification

- Unit test: Verify dispatcher uses `USE_CASE_MAP` for lookups
- Unit test: Verify all MessageSemantics enum values have use-case entries
- Unit test: Verify `VultronApiHandlerNotFoundError` raised for missing semantic types

### DR-03-001, DR-03-002 Verification

- Unit test: Verify DirectActivityDispatcher executes handlers synchronously
- Unit test: Verify exceptions from handlers are caught and logged
- Integration test: Verify error logging contains exception details

### DR-04-001, DR-04-002 Verification

- Integration test: Verify async dispatcher queues multiple activities
- Integration test: Verify activities processed in submission order

## Related

- Implementation: `vultron/core/dispatcher.py`
- Implementation: `vultron/core/use_cases/use_case_map.py` (`USE_CASE_MAP` registry)
- Tests: `test/api/v2/backend/test_dispatch_routing.py`
- Related Spec: [semantic-extraction.md](semantic-extraction.md)
- Related Spec: [handler-protocol.md](handler-protocol.md)
