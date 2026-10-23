---
source: NOTES-federation-ideas--dm-only-communication
timestamp: '2026-09-17T17:25:20.325336+00:00'
title: DM-Only Communication Model
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) delivered
**Superseded by:** notes/case-communication-model.md

---

## 6. DM-Only Communication Model

- After case creation, all case communication is **direct messages** between
  individual participant Actors and the CaseActor. Nothing is broadcast
  publicly.
- CaseActor acts as a **cryptographic hub**: it is the single addressed
  recipient of participant messages, and the single sender of fan-out to
  participants.
- Participants cannot message each other directly within a case — all
  communication routes through CaseActor.
- This means:
  - CaseActor can enforce authorization (Participant role controls what
      actions are permitted).
  - CaseActor attests to ordering and delivery.
  - Participants cannot spoof messages to each other.
  - CaseActor must relay messages to participants (e.g., by `Announce`ing
      them to the participant Actors as DMs), which adds a slight delay but
      ensures consistency.
