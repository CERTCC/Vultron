---
source: NOTES-case-event-history--two-clocks-stay-two-fields
timestamp: '2026-11-16T18:30:57.442900+00:00'
title: Two Clocks Stay Two Fields
type: note
---

**Archived:** 2026-11-16
**Reason:** redundant — captured in CEH-03-007, CEH-03-008 and docs/topics/measuring_cvd/what_a_case_records.md

---

## Two Clocks Stay Two Fields

Carry the commit stamp and the claimed time in separate fields and never substitute
one for the other (CEH-03-008). They come from different clocks and answer different
questions: all commit stamps in a case come from the CASE_MANAGER's one clock, so any
two of them compare; claimed times from two senders do not (CLP-14-003, CLP-15-003).
An interval inside one participant is better measured on claimed times, because a
fixed offset in that participant's clock cancels out.

A reader that cannot tell which clock a value came from cannot judge whether an
interval means anything, so a single merged time field would make every measure
unfalsifiable.

The claimed-time field is absent-able even though a conforming entry always states one
(CLP-15-006, and CLP-15-008 refuses an inbound activity carrying no `published`). This
layer is handed archived and foreign ledgers it never validated, and an absent claimed
time has to read as absent rather than as a commit stamp copied into its place
(CEH-03-007, CEH-03-008).
