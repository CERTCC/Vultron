---
title: "EP-09-002 says the CASE_MANAGER invites every participant except the proposer, but the manager is itself a participant it cannot mail — the spec never says whose consent, if any, the manager's own record carries"
type: learning
timestamp: "2026-10-01T00:30:00Z"
source: ISSUE-3913
signal: spec-gap
---

EP-09-002: "the CASE_MANAGER MUST emit an `Invite(EmbargoEvent)` for the
revision to every case participant except the proposer". The manager holds a
participant record in `actor_participant_index` like everyone else, so a literal
reading relays an Invite to the manager itself. ADR-0109 forbids that (a
container never addresses mail to an actor it hosts), and the EP-09-002 marker
test pins exactly two Invites for three non-manager participants, so #3913
excludes the executing manager from the roster alongside the proposer.

What no spec says is what the manager's own consent record means after that.
When the manager is a CaseActor service (ADR-0041) it has no stake and `UNBOUND`
is right. When the creating actor holds `CASE_OWNER` + `CASE_MANAGER`
(CM-02-015) the owner is a real signatory whose consent to a *participant's*
revision is never solicited by the relay and is recorded only when the owner
answers as the decider (EP-09-005). A manager that is a coordinator with its own
embargo stake — neither owner nor service — falls between the two: never
invited, never asked, `UNBOUND` forever unless it proposes. Whether that record
should be moved at the manager's own commit, left `UNBOUND`, or declared
meaningless for the role holder is a decision EP-09 does not make.
