---
source: CONCERN-4959
timestamp: '2026-10-20T19:56:41.701396+00:00'
title: Case trees commit an embargo consequence after the act
type: learning
---

## Concern

PR for #4949 runs every CASE_MANAGER embargo tree's act and the consequences its later nodes commit in one `ActTransaction` (CLP-07-015, ADR-0146 revision 3). Three case trees also commit an embargo consequence in a later node, each in its own transaction after the act it follows:

- The stub Invite Accept tree (`create_accept_invite_actor_to_case_tree`, `vultron/core/behaviors/case/accept_invite_tree.py`) relays every open proposal to the joiner (`RelayOpenProposalsToJoinerNode`, EP-09-011) after the join has committed.
- The case-participant reinstatement tree (`vultron/core/behaviors/case/case_participant_received_tree.py`) invites the reinstated participant to the embargo (`InviteReinstatedParticipantToEmbargoNode`) after the reinstatement has committed.
- The case-proposal tree relays the creation-time revision (`RelayCreationTimeRevisionNode`, EP-04-011) after the case's creation entries commit. A failed relay is kept as a stored `PendingCreationTimeRevisionRelay` marker that a later delivery or the startup runner (`retry_pending_creation_time_revision_relays`) finishes: a stored plan and a later-run finish, which the maintainer's rule for embargo acts forbids.

When one of these later nodes fails, the act stays committed and the consequence is missing.

## Why it matters

The maintainer's rule is that an act's consequences commit all at once or not at all, with no stored plan and no "a later run finishes it". These trees are case trees, not embargo trees, so #4949 left them out of scope.

## Suggested approach

- Decide whether the rule covers these case trees. If it does, compose each tree's act and the later node with `as_one_act=True` on `create_receive_activity_tree` (renamed from `manager_effects_as_one_act` by the #4933 PR; it now also runs the received act's own guarded commit in the same `ActTransaction`, ADR-0151), as the embargo trees do.
- For the creation-time revision relay, run the case's creation commit and the relay in one transaction, then retire the marker and its startup runner. Retiring the stored marker is a stored-shape change, so it needs explicit instruction (`notes/datalayer-design.md` § "Renaming a Stored Field"); see also #4950.

Governing specs: CLP-07-015, EP-09-011, EP-04-011, CM-14-007

Where: vultron/core/behaviors/case/accept_invite_tree.py, vultron/core/behaviors/case/case_participant_received_tree.py, vultron/core/behaviors/case/nodes/embargo_revision_relay.py

**Resolved**: 2026-10-20 — implementation tracked in #4983, #4984.

The planning interview widened the rule from embargo acts to every received
CASE_MANAGER act. One-act becomes the factory default, with a pinned,
reasoned opt-out (#4983). It also approved retiring both case-creation stored
markers, `PendingCreationTimeRevisionRelay` and `PendingCreateCaseActivity`, by
running case creation as one `ActTransaction` (#4984). Both tasks are blocked
by #4933 (PR #4979), which is rewriting CLP-07-015, ADR-0146 and
`ActTransaction`.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4982>.
