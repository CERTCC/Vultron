# Transfer Handlers Specification

## Context

Transfer handlers manage ownership transfers of cases and reports between participants. Ownership transfers occur when the primary responsible party changes.

## Requirements

### TH-1: OFFER_CASE_OWNERSHIP_TRANSFER Handler - Propose ownership transfer
### TH-2: ACCEPT_CASE_OWNERSHIP_TRANSFER Handler - Accept and complete transfer
### TH-3: REJECT_CASE_OWNERSHIP_TRANSFER Handler - Reject transfer offer
### TH-4: OFFER_REPORT_OWNERSHIP_TRANSFER Handler - Propose report ownership transfer
### TH-5: ACCEPT_REPORT_OWNERSHIP_TRANSFER Handler - Accept report transfer
### TH-6: REJECT_REPORT_OWNERSHIP_TRANSFER Handler - Reject report transfer
### TH-7: Transfer Authorization - Validate transfer authority
### TH-8: Transfer Rollback - Rollback on failure
### TH-9: Multi-Owner Cases - Support partial ownership transfers

## Verification

See full specification for detailed verification criteria.

## Related

- Implementation: `vultron/api/v2/backend/handlers.py`
- Related Spec: [handler-protocol.md](handler-protocol.md)
- Related Spec: [case-handlers.md](case-handlers.md)

