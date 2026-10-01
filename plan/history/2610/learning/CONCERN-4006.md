---
source: CONCERN-4006
timestamp: '2026-10-01T17:36:03.849569+00:00'
title: 'Joining a case: stub Invite, inert participant, full-case Invite'
type: learning
---

## Observation

Driving `POST /actors/{actor_id}/trigger/add-on-behalf-status` end to end (#3832, AC-5) showed that a Case Manager asserting `d_state="D"` on behalf of a deployer that has never joined the case is refused by `CreateParticipantStatusNode` with the cross-machine entailment from `rm_em_cs.md` § Fix Deployment:

> D='D' (D bit set) requires RM ∈ {ACCEPTED, DEFERRED, CLOSED}, but RM='START'.

`EnsureOnBehalfParticipantExistsNode` mints a minimal participant for an absent target (ADR-0084), and a minimal participant sits at `RM.START`, so the on-behalf d→D for a never-joined deployer is refused by construction. It succeeds only for a deployer who already accepted the case and has not self-reported deployment. `test/adapters/driving/fastapi/routers/test_trigger_add_on_behalf_status.py` pins both outcomes.

## Why it is a concern

PRM-06-003 scopes v→V to "a vendor notified or invited but not yet — or never — a participant"; PRM-06-004 says d→D is permitted "under the same externally-evidenced pattern". Read literally, "the same pattern" includes the never-a-participant case, and for d→D that case cannot be written. Nothing in PRM-06 names the entailment and nothing in CSB names the on-behalf carve-out, so a reader of either alone concludes the other allows more than it does.

## Resolution options

1. Amend PRM-06-004 to scope the on-behalf d→D to a deployer who has already accepted the case, naming the entailment as the reason ("expected to be rare" then has a mechanism behind it).
2. Decide under ADR-0084 that an externally evidenced deployment by a never-joined deployer should also carry the RM the evidence implies — a design choice, not a wording fix.

# 3832 took reading 1 in its tests without amending the spec; the learning `plan/incoming/learnings/20260930-3832-prm-06-004-on-behalf-d-to-d-is-unreachable-for-a-never-joined-deployer.md` records the evidence

Governing specs: PRM-06-003, PRM-06-004, CSB-15-004

---

**Resolved**: 2026-10-01 — implementation tracked in issues 4044–4052:

- #4044, #4045, #4046, #4047, #4048, #4049, #4050, #4051, #4052.

Planning showed the concern sat on a misunderstanding of how an actor joins a
case. The participant record was created on `Accept(Invite)`, so roster
membership stood in for embargo consent. An invitee validated the reporter's
original Offer, which was never sent to it. On-behalf status minted
participants. The stub and the case were indistinguishable on the wire, and RM
had no `R → C`. The plan:

- The stub Invite creates an inert participant record.
- A joined participant judges the case by answering a full-case Invite that
  carries a ledger-position floor.
- On-behalf status targets existing participants only.
- RM gains `R → C`; `V → C` stays out, per VP-02-004.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4043>.
ADRs: `docs/adr/0114-joining-a-case-stub-invite-inert-participant.md` (new),
`docs/adr/0070-invited-actor-rm-triage-via-ledger-backfill.md` and
`docs/adr/0084-participant-assertion-authority.md` (rewritten in place).
Notes: `notes/case-joining.md`.
