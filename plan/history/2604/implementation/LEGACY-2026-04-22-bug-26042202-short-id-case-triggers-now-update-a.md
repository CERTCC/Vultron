---
title: BUG-26042202 short-ID case triggers now update actor outboxes
type: implementation
date: '2026-04-22'
source: LEGACY-2026-04-22-bug-26042202-short-id-case-triggers-now-update-a
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7741
legacy_heading: "2026-04-22 \u2014 BUG-26042202 short-ID case triggers now\
  \ update actor outboxes"
date_source: git-blame
legacy_heading_dates:
- '2026-04-22'
---

## BUG-26042202 short-ID case triggers now update actor outboxes

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7741`
**Canonical date**: 2026-04-22 (git blame)
**Legacy heading**

```text
2026-04-22 — BUG-26042202 short-ID case triggers now update actor outboxes
```

**Legacy heading dates**: 2026-04-22

- Issue: trigger-driven create-case and add-report-to-case requests could
  resolve actors from a short URL segment, but then passed that unresolved
  short ID into `add_activity_to_outbox`, which skipped the canonical actor
  `outbox.items` update and logged a warning.
- Root cause: unlike the other trigger use cases, `SvcCreateCaseUseCase` and
  `SvcAddReportToCaseUseCase` did not replace `request.actor_id` with
  `actor.id_` after `resolve_actor(...)`.
- Resolution: normalized `actor_id` to the resolved canonical actor URI before
  queueing the activity in both case trigger use cases, and added router
  regressions covering short-ID trigger requests for URL-form actors.
