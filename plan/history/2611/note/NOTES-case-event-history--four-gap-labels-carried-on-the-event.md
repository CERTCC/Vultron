---
source: NOTES-case-event-history--four-gap-labels-carried-on-the-event
timestamp: '2026-11-16T18:30:57.998548+00:00'
title: Four Gap Labels, Carried on the Event
type: note
---

**Archived:** 2026-11-16
**Reason:** redundant — captured in CEH-03-010 to CEH-03-015 and docs/topics/measuring_cvd/what_a_case_records.md

---

## Four Gap Labels, Carried on the Event

A measure built on an event inherits that event's gap, so the label belongs on the
event record rather than in each measure's own prose (CEH-03-010). Four of the gaps
in `what_a_case_records.md` change an event's time:

| Label | What it means |
|---|---|
| Seated at creation | The creation sequence committed this status, so its stamp is the creation time (CM-14-009, CM-14-012) |
| Stamped at adoption | The case's public state changed when the CASE_MANAGER committed its own case status, not when a participant first reported it |
| Stamped when next handled | A passing deadline caused the change, so the stamp may lag it; the event carries the deadline (EMB-13-003, CM-28-015, CEH-03-015) |
| Reported out of band | A public exploit or observed attacks happened outside the protocol, and the delay before the report is not recorded |

The other gaps carry no label because they produce no event: refusals and replay
requests are never ledgered (CLP-02-013), an ownership-transfer expiry changes no
participant record (CM-21-043), and the untimed register and consent rows are the
reason for the join described above rather than a gap in an event.

The "stamped when next handled" label says the stamp may lag the deadline that caused
the change. Put it on every `END_TIME_REACHED` exit the CASE_MANAGER commits, and on
every timed-out invitation (CEH-03-013). EMB-13-003 reaches an end-time exit two ways,
the CASE_MANAGER's own lazy check and an outside request such as a Sentinel's, and the
ledger records both as the same `Remove(EmbargoEvent)` with no requester. So the label
cannot tell the paths apart, and the deadline the event carries (CEH-03-015) is what
gives the true end time. An end-time exit some other actor committed is not labelled.

Where the ledger holds a deadline that bounds the real time better than the stamp,
carry the deadline too (CEH-03-015). An embargo terminated `END_TIME_REACHED` really
ended at the embargo's end time; the commit stamp is only the latest possible end.
The deadline is not always on the entry recording the event: a timed-out invitation
carries none of its own, because CM-28-013 lets only an `INVITED` consent row hold an
RSVP deadline and the row has already moved to `TIMED_OUT`. Carry it forward from the
earlier entry that recorded the invitation.
