# State Handlers Specification

## Context

State handlers manage explicit state transitions for the three Vultron state machines: Report Management (RM), Embargo Management (EM), and Case State (CS).

## Requirements

### SH-1: RM_CLOSE_REPORT Handler - Transition RM to CLOSED
### SH-2: RM_VALIDATE Handler - Transition RM to VALID
### SH-3: RM_INVALIDATE Handler - Transition RM to INVALID
### SH-4: EM_ACCEPT Handler - Record embargo acceptance
### SH-5: EM_REJECT Handler - Transition EM to REJECTED
### SH-6: EM_TERMINATE Handler - Transition EM to EXITED
### SH-7: CS_PUBLISH Handler - Transition CS.P to PUBLIC
### SH-8: CS_DEPLOY_FIX Handler - Transition CS.F to DEPLOYED
### SH-9: CS_EXPLOIT_PUBLIC Handler - Transition CS.X to ACTIVE
### SH-10: CS_ATTACK_OBSERVED Handler - Transition CS.A to ACTIVE
### SH-11: State Transition Validation - Verify valid transitions
### SH-12: State Synchronization - Propagate state changes

## Verification

See full specification for detailed verification criteria.

## Related

- Implementation: `vultron/api/v2/backend/handlers.py`
- Implementation: `vultron/case_states/`
- Related Spec: [handler-protocol.md](handler-protocol.md)
- Related Spec: [state-transitions.md](state-transitions.md)

