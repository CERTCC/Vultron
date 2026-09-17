---
source: NOTES-federation-ideas--case-ownership
timestamp: '2026-09-17T17:25:19.600520+00:00'
title: Case Ownership
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) delivered
**Superseded by:** notes/ownership-transfer.md

---

## 4. Case Ownership

- `attributed_to` on the Case object designates the current owning instance.
- Ownership is always unambiguous — one instance holds it at any moment.
- Ownership transfer follows an `Offer` / `Accept` cycle, after which
  `attributed_to` is updated.
- The full ownership transfer history is auditable from the activity stream.
- Any participant instance can `Create` a Case from a Report — the creating
  instance owns the created case unless/until transferred.
- **Open question**: ownership transfer mechanics for the CaseActor itself (see
  below).
