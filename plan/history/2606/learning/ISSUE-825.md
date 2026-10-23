---
source: ISSUE-825
timestamp: '2026-06-11T18:36:02.801637+00:00'
title: Actor-participant cache checks should fail only on contradictions, not on misses
type: learning
---

## 2026-06-09 ISSUE-825 — Actor-participant cache checks should fail only on contradictions

- Canonical actor→participant resolution should use `case_participants` as the
  source of truth and treat `actor_participant_index` as a derived cache.
- Fail fast when the cache contradicts canonical data (wrong/stale participant),
  but do not treat a missing cache entry as fatal when canonical participant
  data exists.

**Promoted**: 2026-06-11 — captured in `AGENTS.md` pitfall "Case Participant
Lookup Must Fail Fast on Surface Divergence" (updated with cache-miss vs.
contradiction distinction).
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
