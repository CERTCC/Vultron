---
source: NOTES-participant-embargo-consent--answering-the-embargo-in-force
timestamp: '2026-10-12T19:34:43.956227+00:00'
title: Answering the Embargo in Force (EP-09-012)
type: note
---

**Archived:** 2026-10-12
**Reason:** plan content in a guidance note; the work is fully captured by the open issues that track it
**Superseded by:** #4373 (answer the embargo in force by naming the Invite), #4388 (withdraw with `Leave(EmbargoEvent)`); specs EP-09-012, EP-09-013, MSM-07-010; ADR-0122

---

## Answering the Embargo in Force (EP-09-012)

**Status**: Planned — tracked by #4373 and #4388. Today the triggers resolve
open proposals only, and withdrawal is a Reject of the active embargo.

Activation takes a proposal out of `pending_embargo_proposal_index` (EP-08-003),
so the accept and reject triggers cannot reach the embargo in force through it.
A participant whose row for that embargo is still `INVITED` or `TIMED_OUT` can
still answer it: the receive side marks the row of whatever embargo the
`Accept(Invite(EmbargoEvent))` names, active or not (MSM-07-003, EMB-17-002).

- The answer goes through the relayed `Invite(EmbargoEvent)`, never the
  full-case Invite. Replies to the full-case Invite move only the RM state
  (CM-11-011) and carry no embargo consent.
- A joiner that accepts the stub Invite is already `AGREED` for the active
  embargo (CM-11-001). A joiner's `INVITED` row from the stub Invite
  (CM-11-006) has no `Invite(EmbargoEvent)` behind it, so only a participant
  that never answered a relayed `Invite(EmbargoEvent)` (EP-09-011) needs this.
- The caller names the Invite. With no name the trigger picks among open
  proposals only (EP-08-002) and never falls back to the embargo in force,
  because answering an embargo is an intentional act and a fallback could
  consent to terms the caller did not mean.
- Do not re-add the active embargo to the open-proposal index to make the
  trigger find it; that breaks EP-08-003 and EP-08-002's selection.
- Withdrawing is not answering. A signatory leaves the embargo in force by
  sending `Leave(EmbargoEvent)` through its own trigger (EP-09-013, #4388,
  MSM-07-010), which needs no Invite, so the reporter and a joiner can use it.
  The reject trigger never withdraws, and a Reject of the active embargo from
  an `AGREED` row is refused (MSM-07-004). ADR-0122 records why `Leave` was
  chosen over `Reject(Invite)`, `Undo(Accept)` and `Reject(EmbargoEvent)`.

*Spec: EP-09-012, EP-09-013, EP-08-003, MSM-07-003, MSM-07-010. Decision: ADR-0122.*
