---
source: NOTES-actor-knowledge-model--decision-table
timestamp: '2026-10-12T20:11:14.701135+00:00'
title: Decision Table
type: note
---

**Archived:** 2026-10-12
**Reason:** decision table restated rules the trimmed note and AKM specs state directly
**Superseded by:** specs/actor-knowledge-model.yaml; notes/actor-knowledge-model.md

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Can Actors access each other's DataLayers under any circumstances? | No — never. | Architectural invariant, not an optimization. Even co-located actors must use the wire protocol. |
| Is the "round-trip to the sender's DataLayer" framing correct? | No — that framing implies access is possible but avoided for efficiency. Replace with "the recipient has no access to the sender's DataLayer". | Prevents agents and developers from treating DataLayer isolation as optional. |
| Should outbound activities include full inline objects? | Yes — always, with one approved exception (stub objects in `Invite.target`). | Recipients cannot resolve bare URIs without access to the sender's DataLayer, which they do not have. |
| Where is the authoritative runtime guard? | `outbox_handler.py` raises `VultronOutboxObjectIntegrityError` when `object_` is a bare string or `as_Link` after expansion. | Last-resort catch for code paths that bypass Pydantic construction-time narrowing. |
| Should we track what objects have been shared to avoid redundant transmission? | Deferred to `PROD_ONLY` MAY. Default is "always include full object when in doubt". | Premature optimization; adds bookkeeping complexity not justified at prototype stage. |

---
