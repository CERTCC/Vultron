---
source: NOTES-user-story-catalog--seed-stories
timestamp: '2026-11-04T02:52:37.601346+00:00'
title: 'User story catalog: seed stories'
type: note
---

**Archived:** 2026-11-04
**Reason:** delivered — the seed stories (#4507) are cited by the drafting Tasks; the generated story table is the index of every story, seed or not
**Superseded by:** notes/user-story-catalog.md (now `kind: guidance`), docs/reference/user_stories/ (generated table and traceability matrix)

---

## Seed stories

The seed stories distilled from the five SR-11 gap Ideas and #4487 are
`story_2026_010`–`story_2026_027` (#4507). The area Tasks cite them before
adding new ones; the prefixes are the expected citers, not a commitment.

| Stories | Speaker | Expected citers |
|---|---|---|
| 010, 011, 012 | Peer Implementer: response encoding, semantic wire mapping, datetime serialization | RF, VAM, MSM, DUR, CS |
| 013, 014 | Peer Implementer: malformed-activity rule, idempotency | VAM, MV, SE, IE, CM-13, OX |
| 015, 016 | Peer Implementer: commit before announce, URI round-trip | CM-16, CM-17, OX-03, CLP, OID, VM |
| 017, 018, 019 | Node Operator: HTTP error statuses, log identifiers, timeouts | IE, ENC, SL, CLP-06, SYNC-05 |
| 020, 021 | Tool Author: semantic registry, OpenAPI schema | SE, VAM-01, AR |
| 022 | Protocol Author: case state invariants | CSB-17–19, SM |
| 023 | Auditor: append-only single-writer ledger (took part of 045) | CLP, SYNC, VP-17, CM-02 |
| 024 | Participant: timezone-aware embargo deadlines | DUR-06, CM-28 |
| 025, 026, 027 | Contributor / Maintainer: requirement rationale, ratchet gates, generated traceability | SR-11, MS-10, MS-12-007, MS-12-008, TRACE |
