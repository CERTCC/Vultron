---
title: "EP-04-011 says the CASE_MANAGER commits the creation-time revision 'as a proposal entry', but never says whether the committed relayed Invite is that entry or a second, distinct one is required"
type: learning
timestamp: "2026-10-02T03:00:00Z"
source: ISSUE-3916
signal: spec-ambiguity
---

EP-04-011 (and ADR-0113 detail 9) has the CASE_MANAGER relay the shortest-wins
loser at case creation and commit it "as a proposal entry". For a received
proposal there are two entries: the guarded commit of the inbound `Invite`
(the proposal) and one commit per relayed `Invite`. At creation there is no
inbound Invite, so there is no first entry to commit.

PR #4122 reads the clause as satisfied by the relayed Invite alone: it carries
the pre-indexed proposal id, it is committed in the emitting tree, and #4099's
replay recognises it as a CM-authored entry whose `attributedTo` differs from its
`actor`. A reader who takes "proposal entry" as a separate entry type would find a
gap. The spec should say which it means; if a distinct entry is intended, the
replica replay (#4099) is where it would be consumed.
