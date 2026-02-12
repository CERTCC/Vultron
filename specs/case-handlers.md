# Case Handlers Specification

## Context

Case handlers manage the lifecycle of vulnerability cases, which coordinate disclosure activities across multiple participants.

## Requirements

### CH-1: CREATE_CASE Handler - Create case with initialized state machines
### CH-2: ADD_PARTICIPANT Handler - Add participant to case with role
### CH-3: REMOVE_PARTICIPANT Handler - Remove participant (not last OWNER)
### CH-4: READ_CASE Handler - Retrieve case details with authorization
### CH-5: UPDATE_CASE Handler - Update case fields (not state machine)
### CH-6: CLOSE_CASE Handler - Close case when all reports closed
### CH-7: TRANSFER_CASE_OWNERSHIP Handler - Transfer ownership between participants
### CH-8: Case State Synchronization - Sync state across participants
### CH-9: Multi-Party Coordination - Support multiple vendors/coordinators

## Verification

See full specification for detailed verification criteria.

## Related

- Implementation: `vultron/api/v2/backend/handlers.py`
- Implementation: `vultron/case_states/`
- Related Spec: [handler-protocol.md](handler-protocol.md)
- Related Spec: [state-transitions.md](state-transitions.md)

