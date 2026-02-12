# State Transitions Specification

## Context

The Vultron protocol uses three interacting state machines: Report Management (RM), Embargo Management (EM), and Case State (CS). This specification defines valid state transitions and synchronization requirements.

## Requirements

### ST-1: Report Management (RM) State Transitions
Valid transitions: START→RECEIVED, RECEIVED→INVALID/VALID, VALID→DEFERRED/ACCEPTED, ACCEPTED/DEFERRED→CLOSED

### ST-2: Embargo Management (EM) State Transitions
Valid transitions: NONE→PROPOSED, PROPOSED→ACTIVE/REJECTED/REVISE, REVISE→ACTIVE/REJECTED, ACTIVE→EXITED

### ST-3: Case State (CS) Component Transitions
Valid transitions: v→V (Vendor aware), f→F→x (Fix ready→deployed), d→D→p→P (Disclosure stages), x→X (Exploit public), a→A (Attack observed)

### ST-4: CS Composite State
Composite state notation: vfdxa (initial) → Vfdxa → VFpxa → VFPxa

### ST-5: Transition Guards
Validate guard conditions before transitions (e.g., EM PROPOSED→ACTIVE requires all acceptances)

### ST-6: Invalid Transition Handling
Prevent invalid transitions, raise TransitionValidationError, log at WARNING level

### ST-7: State Machine Synchronization
Synchronize RM, EM, and CS state changes across machines

### ST-8: Multi-Party State Consistency
Maintain consistent state across all participants in multi-party cases

### ST-9: State History
Record timestamp, actor, old/new state, and trigger for each transition

### ST-10: Rollback Support
Support administrative rollback to previous state when safe

## Verification

See full specification for detailed verification criteria.

## Related

- Implementation: `vultron/bt/report_management/states.py`
- Implementation: `vultron/bt/embargo_management/states.py`
- Implementation: `vultron/case_states/states.py`
- Implementation: `vultron/case_states/errors.py`
- Tests: `test/case_states/`
- Related Spec: [state-handlers.md](state-handlers.md)
- Related Spec: [state-persistence.md](state-persistence.md)

