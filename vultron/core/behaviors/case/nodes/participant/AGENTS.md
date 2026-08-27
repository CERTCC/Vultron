# AGENTS.md — `vultron/core/behaviors/case/nodes/participant/`

Agent guidance for participant-lookup BT nodes in this package.

> For project-wide BT conventions see
> [`vultron/core/behaviors/AGENTS.md`](../../../AGENTS.md).

---

## Lenient vs. Strict Participant Lookup Node Variants

(ISSUE-710, 2026-06-09)

Two distinct lookup patterns exist for resolving a participant from an
actor ID:

- **Strict** (`LookupParticipantNode`, fail-on-missing): Required for
  operations that must have a participant record (e.g., recording acceptance).
  Returns `FAILURE` when the participant is not found.
- **Lenient** (`OptionalLookupParticipantNode`, succeed-on-missing): Correct
  for operations where the participant may not exist on this peer yet (e.g.,
  processing an invite or reject). Returns `SUCCESS` even when the participant
  is absent, so the broadcast log entry can proceed.

**Why "Always SUCCESS" is intentional for the lenient variant**: When a
peer receives a log entry for a participant it has not yet seen, succeeding
allows the case ledger cascade to proceed. The state gap resolves when the
participant is later introduced via the normal invite/accept flow.

**Documentation rule**: The docstring for any lenient node MUST explicitly
state that it always returns `SUCCESS` and explain *why* this is correct for
its use case — so future reviewers understand it is a deliberate design
choice, not a missing failure check.

**Constructor parameter audit**: When migrating procedural logic to BT
nodes, verify that all constructor parameters are actually used inside the
node. An unused parameter creates confusion about whether it controls behavior.

**Actor ID handoff in invite trees**: When the invitee actor ID differs
from the sender actor ID, pass the *invitee* ID (not the sender) to
`bridge.execute_with_setup()` so participant-lookup nodes resolve the
correct participant record.
