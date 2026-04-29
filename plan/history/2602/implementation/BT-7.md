---
title: "BT-7 \u2014 Suggest Actor + Ownership Transfer"
type: implementation
date: '2026-02-24'
source: BT-7
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 109
legacy_heading: "Phase BT-7 \u2014 Suggest Actor + Ownership Transfer (COMPLETE\
  \ 2026-02-24)"
date_source: git-blame
legacy_heading_dates:
- '2026-02-24'
---

## BT-7 — Suggest Actor + Ownership Transfer

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:109`
**Canonical date**: 2026-02-24 (git blame)
**Legacy heading**

```text
Phase BT-7 — Suggest Actor + Ownership Transfer (COMPLETE 2026-02-24)
```

**Legacy heading dates**: 2026-02-24

- Handlers: `suggest_actor_to_case`, `accept_suggest_actor_to_case`,
  `reject_suggest_actor_to_case`, `offer_case_ownership_transfer`,
  `accept_case_ownership_transfer`, `reject_case_ownership_transfer`
- `suggest_actor_demo.py` + dockerized
- `transfer_ownership_demo.py` + dockerized
- Bug fix: `AcceptActorRecommendation`/`RejectActorRecommendation` wrap the
  `RecommendActor` Offer as their `object` (consistent with other Accept/Reject pairs)
- Bug fix: `match_field` in `activity_patterns.py` handles string URI refs
  before `ActivityPattern` check
- 525 tests passing at completion; subsequently grown to 554 passing
