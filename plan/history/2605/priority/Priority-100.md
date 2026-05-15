---
source: Priority-100
timestamp: '2026-05-15T14:42:43.312253+00:00'
title: 'Priority 100: Actor independence'
type: priority
---

Each actor exists in its own behavior tree domain. So Actor A and Actor B
cannot see each other's Behavior Tree blackboard at all. They can only interact
through the Vultron Protocol through passing ActivityStreams messages with
defined semantics. This allows us to have a clean model of individual
actors making independent decisions based on their own internal state.

Implementation Phase OUTBOX-1 logically falls under this priority, because
it's part of getting messages flowing between actors. But it does not
fully achieve this goal by itself.
