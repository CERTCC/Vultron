---
title: Demo scripts must puppeteer actors via trigger endpoints, never spoof via inbox injection
type: learning
timestamp: 2026-07-20
source: ISSUE-1535
---

When building multi-actor demo scripts, always use real HTTP trigger endpoints
(e.g. `POST /{actor_id}/trigger/accept-actor-recommendation`) to provoke actor
behavior.  Never manually construct and POST activities directly to actor inboxes
to fake an approval or state change.

**Why:** Inbox injection bypasses the BT evaluation layer entirely and creates
demos that don't validate the actual behavior tree paths.  The distinction is:
puppeteering = sending a trigger that causes the actor to decide and act;
spoofing = forging the resulting activity as if the actor had already decided.

**How to apply:** Before writing any demo step that involves one actor
"responding" to another, check whether the trigger endpoint for that response
exists.  If it doesn't, implement it first (full hexagonal stack) before writing
the demo step.  This surfaced for ISSUE-1535 when no
`accept-actor-recommendation` endpoint existed — implementing the endpoint was
part of the demo task, not a blocker to work around.
