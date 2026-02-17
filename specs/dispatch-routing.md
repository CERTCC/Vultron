# Dispatch Routing Specification

## Overview

After semantic extraction, the dispatcher routes DispatchActivity objects to appropriate handler functions. The dispatcher may execute handlers synchronously (DirectActivityDispatcher) or asynchronously (queue-based).

**Source**: Design documents, handler protocol requirements

---

## Dispatcher Protocol (MUST)

- `DR-01-001` All dispatcher implementations MUST implement ActivityDispatcher protocol
- `DR-01-002` Dispatchers MUST pass complete DispatchActivity objects when invoking handlers
- `DR-01-003` Dispatchers MUST invoke `verify_semantics` decorator checks during handler execution

## Handler Lookup (MUST)

- `DR-02-001` The system MUST look up handler functions by semantic type using `SEMANTIC_HANDLER_MAP`
- `DR-02-002` SEMANTIC_HANDLER_MAP MUST contain entries for all MessageSemantics values

## Direct Dispatch Implementation (MUST)

- `DR-03-001` The DirectActivityDispatcher MUST execute handlers synchronously
- `DR-03-002` The DirectActivityDispatcher MUST catch and log handler exceptions at ERROR level
  - **Cross-reference**: See `structured-logging.md` SL-03-001 for log level semantics and `error-handling.md` EH-06-001 for exception logging requirements
  - **Verification**: Logged exceptions include handler name, activity ID, and full error context

## Async Dispatch Implementation (SHOULD)

- `DR-04-001` An async dispatcher SHOULD queue activities for processing
- `DR-04-002` An async dispatcher SHOULD process activities in FIFO order

## Verification

### DR-01-001, DR-01-002, DR-01-003 Verification
- Unit test: Verify DirectActivityDispatcher implements ActivityDispatcher protocol
- Unit test: Verify dispatcher passes complete DispatchActivity to handlers
- Unit test: Verify decorator validation occurs during dispatch

### DR-02-001, DR-02-002 Verification
- Unit test: Verify dispatcher uses SEMANTIC_HANDLER_MAP for lookups
- Unit test: Verify all MessageSemantics enum values have handler entries
- Unit test: Verify KeyError raised for missing semantic types

### DR-03-001, DR-03-002 Verification
- Unit test: Verify DirectActivityDispatcher executes handlers synchronously
- Unit test: Verify exceptions from handlers are caught and logged
- Integration test: Verify error logging contains exception details

### DR-04-001, DR-04-002 Verification
- Integration test: Verify async dispatcher queues multiple activities
- Integration test: Verify activities processed in submission order

## Related

- Implementation: `vultron/api/v2/backend/behavior_dispatcher.py`
- Implementation: `vultron/api/v2/backend/semantic_handler_map.py`
- Tests: `test/api/v2/backend/test_dispatch_routing.py`
- Related Spec: [semantic-extraction.md](semantic-extraction.md)
- Related Spec: [handler-protocol.md](handler-protocol.md)
