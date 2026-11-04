---
source: NOTES-user-story-catalog--what-was-measured
timestamp: '2026-11-04T02:52:36.501376+00:00'
title: 'User story catalog: what was measured (2026-10-12)'
type: note
---

**Archived:** 2026-11-04
**Reason:** delivered — the plan the note informed (Epic #2717, last Task #4516) has landed; the baseline figures describe the start of that plan, not a rule
**Superseded by:** notes/user-story-catalog.md (now `kind: guidance`), docs/reference/user_stories/ (generated table and traceability matrix)

---

The pages under `docs/reference/user_stories/` are the only "why" a protocol
requirement can cite (SR-11). This note records how the catalog is kept and how
the protocol requirements that have no story get one. The planning decisions
were made on 2026-10-12 from the Concern #4487 and the five SR-11 gap
Ideas #2596–#2600; the measurements below are from the same day.

## What was measured

| Fact | Figure (2026-10-12) |
|---|---|
| Protocol requirements with no `stories:` | 488 of 1,286 |
| … of which binding (`MUST` 135, `MUST_NOT` 128) | 263 |
| … of which advisory tier (`SHOULD`, `SHOULD_NOT`, `MAY`) | 225 |
| `missing_story_reference` suppressions (all `kind: protocol`: 135 `MUST`, 4 `MUST_NOT`, 2 `MAY`) | 141 (ratchet ceiling) |
| Requirements citing a story (798 protocol, 3 project) | 801 |
| Requirement IDs the hand-edited traceability matrix links | 161 |
| Stories whose text starts "As a Participant" | 84 of 111 |
| Citations carried by stories 088, 045 and 014 together | 419 |
| Stories no requirement cites (all five about bounties) | 5 |

Two of those rows are the reason this note exists. The matrix that TRACE-01
calls the traceability record links one fifth of the requirements that
actually carry a story: it was hand-edited after ADR-0072 made the spec files
authoritative, so it can only drift. And the five Ideas each carry a spec list
from the 2026-08-25 mapping pass; about a third of the IDs on those lists have
since been relabeled to `kind: project` or deleted, so the lists cannot drive
the work. The spec registry can.
