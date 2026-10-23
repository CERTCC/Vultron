---
source: ISSUE-4291
timestamp: '2026-10-08T16:08:00.004708+00:00'
title: 'Superseded: No Row Means Not Bound by Any Embargo Terms'
type: note
---

Archived from `notes/participant-embargo-consent.md` (issue #4291, ADR-0122 revision 2):
every consent row is now written, starting at `UNINVITED`, so "no row" no longer
means "not asked"; a missing row is a defect and reading one raises.

## No Row Means Not Bound by Any Embargo Terms

*Spec: CM-18-001, CM-18-003. Decisions: ADR-0048, ADR-0091, ADR-0122.*

A participant with no row for an embargo is **not bound by it**. That does *not*
mean "has not consented yet, and an invitation is owed". Read the second way, it
implies every consent must be preceded by an invitation — which is false:

- A Finder who creates a case for their own finding and sets its default
  embargo has **no inviter**.
- Participants added during case initialization (ADR-0041) already have an
  embargo in scope from the moment they exist, because the CASE_MANAGER
  initializes the default embargo in the same BT sequence.
- The reporter's consent is **implicit** in submitting the report (CM-14-005);
  no invitation is ever sent.

So `ACCEPT` and `DECLINE` are valid directly from no row. Requiring a synthetic
`INVITED` hop for these paths would write an invitation event into the canonical
ledger that never occurred (contra ADR-0019). `CaseParticipant.sign_embargo()` is
that seeding shape: `ACCEPT` where legal, and a no-op (no row written) when no embargo
is in force.

**What this costs:** the machine does not enforce "consent implies a prior
invitation". That invariant was never true of self-determined embargoes, so the
enforcement would have been spurious — but treat any code that leaned on it as
suspect.
