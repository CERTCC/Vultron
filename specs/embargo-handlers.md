# Embargo Handlers Specification

## Context

Embargo handlers manage coordinated disclosure timelines. Embargoes define periods during which vulnerability information must remain confidential among case participants.

## Requirements

### EH-1: PROPOSE_EMBARGO Handler - Create embargo proposal with dates
### EH-2: ACCEPT_EMBARGO Handler - Record participant acceptance
### EH-3: REJECT_EMBARGO Handler - Record rejection with reason
### EH-4: ACTIVATE_EMBARGO Handler - Activate when all accept
### EH-5: REVISE_EMBARGO Handler - Update embargo terms
### EH-6: TERMINATE_EMBARGO Handler - End embargo early
### EH-7: EMBARGO_EXPIRATION Handler - Auto-expire at end date
### EH-8: Embargo Violation Detection - Monitor for violations
### EH-9: Multi-Embargo Cases - Track multiple embargo proposals

## Verification

See full specification for detailed verification criteria.

## Related

- Implementation: `vultron/api/v2/backend/handlers.py`
- Implementation: `vultron/case_states/embargo_management.py`
- Related Spec: [handler-protocol.md](handler-protocol.md)
- Related Spec: [state-transitions.md](state-transitions.md)

