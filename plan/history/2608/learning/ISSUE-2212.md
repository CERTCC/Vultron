---
title: Pre-existing code-review findings from PR #2826 need GitHub tracking
type: learning
timestamp: 2026-08-28T12:00:00Z
source: ISSUE-2212
signal: concern
---

Six pre-existing findings were surfaced by the code-review agent during the
PR #2826 build pass. All are in files not modified by this PR. They were
posted as `[ADVISORY]` in a PR comment but no GitHub issues were created.

The `build` skill Phase 7 requires DEFER findings to be tracked as GitHub
issues immediately. These were treated as ADVISORY instead, which is not a
recognized category.

**Untracked findings:**

1. `vultron/wire/as2/factories/embargo.py:112` — `kwargs.setdefault` allows
   caller-supplied `end_time` to override validated `rsvp_deadline`. Correctness.
2. `vultron/wire/as2/extractor/_extract.py:83` — naive inbound `end_time`
   silently dropped with no diagnostic. Observability gap.
3. `vultron/wire/as2/extractor/_extract.py:87` — floor clamping uses hardcoded
   72h default; actor-configured `min_rsvp_window` not consulted. Correctness.
4. `vultron/demo/scenario/fvv_demo.py:120` — dead code constants after
   migration to `actor.id_`.
5. `.agents/skills/bugfix/REFERENCE.md:51` — `PARENT_ARG` set without
   non-empty guard; empty `ISSUE_NUMBER` produces `--parent` (blank arg).
6. `vultron/demo/scenario/fvv_demo.py:318` — `wait_for_case_participants`
   runs unconditionally after a failed `demo_gate`.

**Action:** Create GitHub Bug/Concern issues for findings 1, 2, 3, 5, 6 (the
substantive correctness and observability gaps). Finding 4 (dead code) can be
bundled with the next demo-cleanup task.

## Audit disposition (2026-09-02)

All six findings were subsequently filed by later sessions: #2848 (kwargs.setdefault end_time), #2849 (naive end_time dropped), #2850 (RSVP 72h floor ignores min_rsvp_window), #2851 (PARENT_ARG unguarded), #2852 (wait_for_case_participants after failed gate). The dead-code constants were absorbed into demo cleanup. Note that none were filed from this entry — the queue was not the mechanism.
