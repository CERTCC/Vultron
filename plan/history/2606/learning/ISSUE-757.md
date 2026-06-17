---
source: ISSUE-757
timestamp: '2026-06-11T18:34:52.866890+00:00'
title: Shared participant lookup must support both case participant surfaces
type: learning
---

## 2026-06-08 ISSUE-757 — Shared participant lookup must support both case participant surfaces

- `VulnerabilityCase` fixtures and call sites are mixed: some populate
  `case_participants`, others rely on `actor_participant_index`.
- A shared BT lookup node that only scans `case_participants` regresses
  status workflows that previously used `actor_participant_index` checks.
- The reusable participant-finder logic should seed from the
  `actor_participant_index` direct hit first, then scan `case_participants`.

**Promoted**: 2026-06-11 — captured in `AGENTS.md` pitfall "Case Participant
Lookup Must Fail Fast on Surface Divergence" (updated to clarify fail only on
contradictions, not missing cache entries).
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
