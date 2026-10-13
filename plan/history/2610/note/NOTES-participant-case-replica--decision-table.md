---
source: NOTES-participant-case-replica--decision-table
timestamp: '2026-10-12T19:35:05.858100+00:00'
title: Decision Table
type: note
---

**Archived:** 2026-10-12
**Reason:** summary of decisions now stated as rules in the note body and in specs
**Superseded by:** specs/participant-case-replica.yaml; notes/participant-case-replica.md

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Does each participant need a stub CASE_MANAGER clone? | No — one Actor, one inbox; routing is an internal concern. | Separate per-participant-per-case actors would explode the actor registry and add wire-protocol complexity with no protocol benefit. |
| What is the bootstrap mechanism for delivering a full case snapshot? | Split by path: creator-signed `Create(VulnerabilityCase)` for the original report path; `Announce(VulnerabilityCase)` from the CASE_MANAGER after trust is established; invite-based bootstrap for late joiners. | Original report submitters already trust the report receiver, so that actor should introduce the CASE_MANAGER. Late joiners need trust establishment through invitation rather than report history. |
| Who triggers initial sync for the original participants? | The report receiver sends one-time `Create(VulnerabilityCase)` to the original report submitter (ADR-0132). | This establishes trust in the CASE_MANAGER before later updates arrive from a different identity. |
| Who triggers initial sync for late-joining participants? | The case creator establishes trust through `InviteActorToCase`, then the CASE_MANAGER sends `Announce(VulnerabilityCase)` after acceptance. | Keeps late-joiner trust establishment tied to the invite flow while preserving CASE_MANAGER-authoritative replication afterward. |
| Who may update a participant's local case replica? | Only the CASE_MANAGER. Reject and log at WARNING for any other sender. | Enforces the single-writer invariant (CM-02-002). Matches the idea's explicit requirement. |
| Does the case owner follow the same replica rules? | Yes. Even the case owner routes through the CASE_MANAGER and never writes directly to its local copy. | Holds whether the owner and CASE_MANAGER are two actors or one (CM-02-010 allows both); the owner's writes pass through the CASE_MANAGER role either way. |
| Which field routes a case-scoped message to the right local handler? | `context` field, set to the case ID. | Already the established pattern in all demos. Consistent with AS2 semantics. |
| What happens when an activity arrives with an unknown case context? | Queue, warn, request resync. Drop if no snapshot arrives within timeout. | Handles out-of-order delivery (snapshot and follow-up arrive in wrong order) without silently dropping or corrupting state. |
| Should an actor maintain a report-to-case mapping? | Yes. Allows reporter actors to recognize that bootstrap `Create(Case)` and later `Announce(Case)` traffic belong to their prior `Offer(Report)`. | Enables the "reporter checks their open submissions" flow described in the idea. |
