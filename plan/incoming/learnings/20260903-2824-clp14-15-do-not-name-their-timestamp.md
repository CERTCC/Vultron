---
title: "CLP-14/CLP-15 constrain two different timestamps without naming which, and CLP-15-001/002 are written as if the CaseActor could enforce what CLP-15-005 forbids it from reconstructing"
type: learning
timestamp: "2026-09-03T20:40:00Z"
source: ISSUE-2824
signal: spec-contradiction
---

A `CaseLedgerEntry` carries two timestamps, and CLP-14/CLP-15 never say which
one each requirement is about:

- `CaseLedgerEntry.published` — the CaseActor's **commit** stamp.
- `payloadSnapshot.published` — the asserting actor's **claimed** event time.

The distinction is not cosmetic. It decides whether a requirement holds by
construction or has to be enforced, and picking the wrong field produces a check
that is either vacuous or falsely rejecting:

| Requirement | Statement says | Which field it can only mean |
|---|---|---|
| CLP-14-002 | "The published timestamp on a `CaseLedgerEntry`" | commit stamp |
| CLP-14-003 | "published timestamps on consecutive recorded entries" | commit stamp — one writer, one clock, so true by construction |
| CLP-14-006 | "Every CaseLedgerEntry's published timestamp" | ambiguous; enforceable only against the claimed time, since the commit stamp is `now()` and trivially satisfies it |
| CLP-14-007/008 | "`payloadSnapshot.published`" | claimed time — the only two that say so explicitly |
| CLP-15-003 | "the published timestamp on activity B" | claimed time |

Applied to the wrong field, CLP-14-003 is actively harmful: comparing *claimed*
timestamps across two participants is exactly the wall-clock ordering ADR-0079
rejected as option C. Participant A stamps T5, B stamps T3, the CaseActor
receives A then B, and a well-formed assertion is rejected because two clocks
disagree. CLP-15-003 is the same property stated correctly — "within the same
participant's event stream" — which is what makes it enforceable where
CLP-14-003 is not.

**The contradiction.** CLP-15-001 ("a participant MUST emit ... in causal
order") and CLP-15-002 ("MUST NOT batch ... in arbitrary order") are written in
a group whose title is *Participant Assertion Timestamp Obligations*, but nothing
in either says who checks them. CLP-15-005, four entries later, says the
CaseActor "MUST NOT attempt to reconstruct participant-internal causal order it
cannot verify." A reader implementing CLP-15-001 per-assertion is implementing
the thing CLP-15-005 prohibits — and it cannot be done anyway, because
`_validate_canonical_entry` is stateless. Seven `xfail(strict=True)` stubs were
written against exactly that reading and could never have gone green.

The consequence obligations *are* observable, just not per-assertion:
`check_causal_edges` (DEMOMA-22-005) compares declared causal edges against
observed ledger order across a whole scenario, which is the only vantage point
from which an emission-order obligation shows up at all.

**How to apply.** Any requirement about a timestamp on an object that carries
more than one MUST name the field. Where a requirement is a *participant*
obligation, it MUST also say what the receiver is expected to do about it —
enforce, flag, or nothing — or the next implementer will read "MUST" as "reject
at the boundary." A group heading is not a substitute: CLP-15's heading did not
stop four entries from being read as CaseActor duties.

Candidate spec work: name the field in CLP-14-002/003/006; give CLP-15-001/002 a
`verification` pointing at `check_causal_edges` and an explicit note that they
are not per-assertion enforceable; consider whether CLP-14-003 should be split
into a commit-stamp entry and a claimed-time entry that defers to CLP-15-003.

Related: [[20260901-2906-emit-receive-invariant-asymmetry]] — the same shape,
a requirement whose enforcing side was left implicit.
