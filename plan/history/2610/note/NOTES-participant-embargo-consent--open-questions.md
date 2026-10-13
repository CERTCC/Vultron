---
source: NOTES-participant-embargo-consent--open-questions
timestamp: '2026-10-12T19:34:44.354822+00:00'
title: Open Questions
type: note
---

**Archived:** 2026-10-12
**Reason:** resolved items are recorded in the specs/ADRs named below; the remaining open items are design questions, not guidance
**Superseded by:** EP-07-001, EP-07-002, EP-07-006, CM-28-011 (timeout defaults); ADR-0096 (no pre-case embargo phase); #2214 (rescind via `Undo(Invite(EmbargoEvent))`); still open: automatic removal of `DECLINED` participants (#4547), and a separate owner notification on `DECLINED`/`TIMED_OUT` (#4548)

---

## Open Questions

- Should `DECLINED` participants be automatically removed from the case, or
  left in the case but excluded from embargo-protected content?
  *Partially resolved*: EMB-17-004 establishes that case participation survives
  an embargo no-op, so removal is not automatic on the late-accept path. The
  general `DECLINED` case is still open.
- Should the case actor notify the case owner when a participant's consent
  state transitions to `DECLINED` or `TIMED_OUT`?
  *Partially resolved*: CM-28-005 requires a CASE_MANAGER-authored ledger entry for
  an expiry, which makes it visible to the owner via the ledger. Whether a
  *separate* notification activity is also warranted is still open.
- ~~What is the default embargo invitation timeout?~~ **Resolved**: EP-07-001
  sets the fallback default at 7 days (matching CM-18-002), superseded by
  `Invite.end_time` when present (CM-28-002). The minimum window is the lesser of
  the configured window (72h by default) and the time remaining in the embargo
  (EP-07-002, amended by ADR-0096), and whichever deadline results is clamped down
  to the embargo's own `end_time` (EP-07-006, CM-28-011). Neither the explicit
  `Invite.end_time` nor the policy window escapes that ceiling — see
  `notes/embargo-default-semantics.md` § "An RSVP Deadline May Not Outlive Its
  Embargo".
- No mechanism exists to **rescind** an unanswered invitation before its
  deadline. `as_Undo` is already in the vocabulary
  (`vultron/wire/as2/vocab/base/objects/activities/transitive.py`), so
  `Undo(Invite(EmbargoEvent))` needs no new noun — but it does need a pattern,
  extractor entry, and use case. Deferred from ADR-0065; tracked as its own
  Idea under epic #2088.
- ~~Embargo negotiation **before** report submission is documented as permitted
  but has no implemented mechanics.~~ **Resolved** by ADR-0096 (CONCERN-2215):
  there is no pre-case EM phase, and there cannot be one. EM is a per-case machine,
  so a `propose` transition before a case exists names a machine instance that
  cannot exist — the defect was unrepresentability, not a lagging implementation.
  `rm_em.md` now states the EM process SHALL NOT begin before a case exists. The
  need it served is met two other ways: a short protocol default means a sender
  always knows the floor (EP-04-005), and a sender states its own terms by
  embedding a proposed `EmbargoEvent` on the report offer (EP-04-004). The second
  of those *does* give pre-case terms a home, so there is no deadline-without-a-case
  problem to solve: the proposal is not an invitation, and the RSVP deadline still
  attaches only to a case-scoped `Invite(EmbargoEvent)`. See ADR-0096, which
  rules out a pre-case embargo phase.
