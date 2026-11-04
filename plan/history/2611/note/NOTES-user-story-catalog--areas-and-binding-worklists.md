---
source: NOTES-user-story-catalog--areas-and-binding-worklists
timestamp: '2026-11-04T02:52:37.238466+00:00'
title: 'User story catalog: areas and their binding worklists'
type: note
---

**Archived:** 2026-11-04
**Reason:** delivered — every drafting Task (#4508, #4510, #4512, #4513) is closed and SR-11-003 now gates the binding tier; the story-gaps report is the live worklist
**Superseded by:** notes/user-story-catalog.md (now `kind: guidance`), docs/reference/user_stories/ (generated table and traceability matrix)

---

## Working the protocol story gap (archived part)

Order relative to the rationale backfill: the rationale backfill for every
area (#4483–#4486) is complete, so no drafting Task waits on it. Every
requirement now carries a rationale (SR-02-009), and it tells the story author
which need the requirement serves.

### Areas and their binding worklists

Measured 2026-10-12; the gap report is authoritative at execution time.

| Area (mirrors the rationale backfill) | Spec prefixes with binding gaps | Binding |
|---|---|---|
| Core protocol text (#4483 files) | MSM 12, ASK 8, DUR 8, AKM 5, EP 4, OID 4, VP 3, ENC 3, LST 3, SDO 3, RF 2 | 55 |
| Ledger and replication (#4484 files, part 1) | CLP 31, SYNC 17, PCR 13, VAM 8, CBT 4, VM 4 | 77 |
| Case management and state machines (#4484 files, part 2) | CM 25, CSB 13, RSH 12, EMB 10, SM 5, PRM 4, CP 4, RMB 3 | 76 |
| Implementation architecture (#4485 files) | SE 15, MV 10, IE 8, TRIG 6, BT 4, OX 3, AR 2, SL 2, BTND 1, EDF 1, CS 1 | 53 |
| Tooling, process and demos (#4486 files) | BW 2 | 2 |

The core protocol area also holds 90 advisory-tier `VP` requirements with no
story: the protocol specification itself. Most should map to existing stories
and are worth the pass even though the tier does not require it.
