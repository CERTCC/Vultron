---
title: No spec forbids a received-side tree from re-emitting another actor's activity or addressing itself
type: learning
timestamp: 2026-09-25T00:00:00Z
source: ISSUE-2667
signal: spec-gap
---

The AckReport received tree emitted `Read(Offer)` on every receipt, under the
receiver's name. That covered acks the receiver did not author. At the
CASE_MANAGER the recipient was itself, so OX-12-004 loopback self-delivery fed
the ack straight back into its inbox, and the cycle never ended. PR #3751 fixed
this with two skips, one for a foreign sender and one for the CASE_MANAGER. No
requirement names either invariant:

- A received-side tree must not re-emit an activity authored by another actor
  as if the executing actor had authored it. BT-17-006 forbids falling back to
  the sender for *identity*. It says nothing about re-publishing the sender's
  *act*.
- An emit must not be addressed only to the executing actor. OX-12-004 makes
  self-delivery legal, so a self-addressed emit on a received path is a loop,
  not a no-op.

The `update_tree` and engage broadcast gates (#3746) and the ungated
suggest-actor trees (#3752) are the same shape. A case-manager role gate is
added one tree at a time, because nothing states the rule it enforces.
Candidate home: a BT-17 or CM-24 statement, plus an architecture ratchet that
flags any received tree whose emit nodes are neither role-gated nor
sender-gated.
