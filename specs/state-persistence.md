# State Persistence Specification

## Context

The Vultron inbox handler must persist case, report, participant, and embargo state to durable storage for recovery, distributed processing, and audit trails.

## Requirements

### SP-1: Database Abstraction - Use repository interfaces for multiple backends
### SP-2: Case Persistence - Store case ID, state machines, participants
### SP-3: Report Persistence - Store report ID, RM state, vulnerability details
### SP-4: Participant Persistence - Store participant roles and links to cases
### SP-5: Embargo Persistence - Store embargo state, dates, acceptances
### SP-6: Activity Persistence - Store processed activities for audit
### SP-7: Transaction Management - Use ACID transactions for state changes
### SP-8: Data Integrity - Enforce foreign keys and constraints
### SP-9: Performance Optimization - Use indexes and connection pooling
### SP-10: Data Migration - Support schema evolution with migrations
### SP-11: Backup and Recovery - Enable automated backups

## Verification

See full specification for detailed verification criteria.

## Related

- Implementation: (Future) `vultron/db/` module
- Implementation: `vultron/api/v2/backend/handlers.py`
- Related Spec: [state-transitions.md](state-transitions.md)
- Related Spec: [concurrency.md](concurrency.md)

