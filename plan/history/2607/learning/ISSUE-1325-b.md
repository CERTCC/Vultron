---
title: "Use disposition=rejected for local-only ledger correlation markers"
type: learning
timestamp: 2026-07-13T00:00:00Z
source: ISSUE-1325-b
---

When a BT node needs to write a local ledger entry that does not correspond
to a canonical AS2 activity (e.g., tracking an outbound "offer_case_participant"
or "invite_actor_to_case" for duplicate detection), use `disposition="rejected"`
in `create_commit_log_entry_tree`.

`_validate_canonical_entry` returns early for non-"recorded" dispositions,
bypassing the `_CANONICAL_PAYLOAD_SIGNATURES` allowlist check.  The entry is
still persisted and `find_protocol_pair` does not filter on disposition, so
the correlation marker is visible to duplicate-detection nodes.

The `_find_equivalent_recorded_entry` idempotency check also filters on
`disposition == "recorded"`, so repeated calls each create a new marker —
which is fine when the BT guarantees at-most-once execution per receipt
(e.g., via GuardedCommit in create_receive_activity_tree).

**Promoted**: 2026-07-15 — captured in notes/bt-integration.md.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1458>8>8>8>8>.
