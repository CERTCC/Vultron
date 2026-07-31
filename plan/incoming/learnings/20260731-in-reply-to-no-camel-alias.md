---
title: "as_Object.in_reply_to has no camelCase alias — inconsistent with AS2 convention"
type: learning
timestamp: "2026-07-31"
source: ISSUE-1834
signal: concern
---

During #1834 review, confirmed that `as_Object.in_reply_to` serializes as
`in_reply_to` (snake_case) via `model_dump(by_alias=True)`, not `inReplyTo`
(camelCase) as the ActivityStreams 2.0 spec requires.

Every other multi-word AS2 field on `as_Object` (`startTime`, `endTime`,
`inReplyTo`, etc.) has a camelCase alias via `alias_generator=to_camel` on the
wire base class — but `in_reply_to` was declared directly on `as_Object` without
an alias, so the alias generator was never applied to it.

Current impact: `PendingCreateCaseActivity.create_activity_payload` stores
`in_reply_to` in snake_case. The retry runner (#1139) that replays this payload
over the wire will send a non-standard key. Recipients expecting `inReplyTo`
per AS2 will silently drop the causal link.

Suggested fix: add `alias="inReplyTo"` (or let `to_camel` handle it) to
`as_Object.in_reply_to`, verify serialization, and update any tests that
assert `payload.get("in_reply_to")` → they should assert `payload.get("inReplyTo")`.
