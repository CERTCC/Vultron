---
source: NOTES-ownership-transfer--analogy-invite-accept-handshake
timestamp: '2026-10-12T19:35:16.798741+00:00'
title: 'Analogy: Invite/Accept Handshake'
type: note
---

**Archived:** 2026-10-12
**Reason:** explanatory analogy, not a rule; the routing rule it illustrates is kept in notes/ownership-transfer.md
**Superseded by:** ADR-0053; docs/topics/case_lifecycle/ownership_transfer.md

---

## Analogy: Invite/Accept Handshake

This routing model is identical to the Invite/Accept handshake (ADR-0026,
PCR-08-007/008):

| Invite/Accept | Ownership Transfer |
|---|---|
| `Invite` sent **by** CASE_MANAGER | `Offer` addressed **to** CASE_MANAGER → forwarded |
| `Accept(Invite)` addressed **to** CASE_MANAGER | `Accept(Offer)` addressed **to** CASE_MANAGER |
| CASE_MANAGER creates `CaseParticipant` | CASE_MANAGER applies CM-21 role changes |
| CaseLedgerEntry → broadcast | CaseLedgerEntry → broadcast |

Use this analogy when explaining the model to new contributors.
