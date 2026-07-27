---
source: CONCERN-1635
timestamp: '2026-07-27T18:34:09.099027+00:00'
title: 'Missing rule: demo scripts must never carry one actor''s mail to another''s
  inbox'
type: learning
---

## Summary

`vultron/demo/AGENTS.md` documented "puppeteer via triggers, never spoof via inbox injection" but said nothing about *how to wait for cross-container delivery*. The implicit constraint that `post_to_inbox_and_wait` must be used for explicit cross-container delivery was documented in CONCERN-1635 as the "correct" pattern.

## Root Cause Discovered

During planning, this turned out to be incorrect. `post_to_inbox_and_wait` is itself a form of spoofing — it acts as a surrogate mail carrier, POST-ing one actor's activity directly to another actor's inbox from outside the real delivery path. This violates the puppeteer-not-spoof principle the existing rule was trying to enforce.

The real root cause of the original PR #1623 bug was a `BackgroundTasks` timing gap: the inbox endpoint returns 202 before processing completes, so naive polling timed out. The "fix" replaced a fragile poll with a layering violation.

The correct pattern is: trigger the sending actor via its trigger endpoint, then poll the receiving actor's DataLayer using existing helpers (`wait_for_case_on_container`, `find_case_invite_for_actor`, `verify_object_stored`) with a sufficient timeout. The real HTTP delivery path (`DemoHttpDeliveryAdapter`) with retry/backoff handles cross-container delivery reliably.

## Resolution

**Resolved**: 2026-07-27 — docs rule added in #1722; implementation (remove all mail-carrying calls from scenario files + investigate BackgroundTasks timing) tracked in #1721.

Docs PR: <https://github.com/CERTCC/Vultron/pull/1722>
