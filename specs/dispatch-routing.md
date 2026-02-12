# Dispatch Routing Specification

## Context

After semantic extraction, the dispatcher routes DispatchActivity objects to appropriate handler functions. The dispatcher may execute handlers synchronously (DirectActivityDispatcher) or asynchronously (queue-based). Handler selection uses the SEMANTIC_HANDLER_MAP registry.

## Requirements

### DR-1: Handler Lookup
The system MUST look up handler functions by semantic type using `SEMANTIC_HANDLER_MAP`.

### DR-2: Direct Dispatch Execution
The DirectActivityDispatcher MUST execute handlers synchronously and capture exceptions.

### DR-3: Async Dispatch Execution
An async dispatcher (future implementation) MUST queue activities and process in FIFO order.

### DR-4: Handler Registry Completeness
SEMANTIC_HANDLER_MAP MUST contain entries for all MessageSemantics values.

### DR-5: Dispatcher Protocol
All dispatcher implementations MUST implement ActivityDispatcher protocol.

### DR-6: Error Propagation
Dispatchers MUST catch and log handler exceptions appropriately.

### DR-7: Handler Invocation Contract
When invoking handlers, dispatchers MUST pass complete DispatchActivity and invoke `verify_semantics` decorator checks.

## Verification

See individual requirement verifications in full specification document.

## Related

- Implementation: `vultron/behavior_dispatcher.py`
- Implementation: `vultron/semantic_handler_map.py`
- Implementation: `vultron/api/v2/backend/handlers.py`
- Tests: `test/test_behavior_dispatcher.py`
- Tests: `test/test_semantic_handler_map.py`
- Related Spec: [semantic-extraction.md](semantic-extraction.md)
- Related Spec: [handler-protocol.md](handler-protocol.md)
- Related Spec: [queue-management.md](queue-management.md)

