---
source: NOTES-federation-ideas--report-to-case-lifecycle
timestamp: '2026-09-17T17:25:20.003915+00:00'
title: Report to Case Lifecycle
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) delivered
**Superseded by:** notes/case-creation-sequence.md superseder notes/case-proposal.md; specs/case-bootstrap-trust.yaml

---

## 5. Report → Case Lifecycle

```text
1. REPORT PHASE
   Alice (VendorA) POSTs Offer{object: Report} to VendorB's instance inbox.
   This is the only "cold contact" — no case exists yet.

2. CASE CREATION
   VendorB accepts → creates Case + CaseActor.
   VendorB POSTs Accept{object: Offer(object: Report)} to 
   Alice.
   VendorB POSTs Create{object: Case} to Alice.
   Alice creates a local mirror of the Case object.
   CaseActor POSTs Add{object: Participant(Alice), target: Case} to Alice.

3. STEADY STATE
   All communication is DMs between participant Actors and CaseActor.
   CaseActor fans out relevant activities to all participants.
   Each participant maintains a local mirror, updated by the DM stream.

4. OWNERSHIP TRANSFER
   CaseActor POSTs Offer{object: Case} to target Actor.
   Target Accepts.
   CaseActor migrates to new owning instance.
```
