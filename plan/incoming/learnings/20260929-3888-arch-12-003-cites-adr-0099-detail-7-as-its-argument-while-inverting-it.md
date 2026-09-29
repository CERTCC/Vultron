---
title: "Closing every issue under an ADR's epic graduates the work items, not the decision details — and a lint_suppress added at graduation silences the one gate that would have asked"
type: learning
timestamp: "2026-09-29T20:30:00Z"
source: ISSUE-3888
signal: theme-candidate
---

ADR-0099 was graduated from `accepted-provisional` to `accepted` in #3491 when
the last migration issue under its epic (#2670) closed. Two of its ten decision
details — 7 (unrecognised fields set aside, not rejected) and 8 (set-aside
fields reported at INFO, near misses warned) — had never been built. What had
been built was the opposite: `extra="forbid"` on every core object (#2940),
which ARCH-12-003 then made a MUST while its rationale cited detail 7 as the
argument it enforced. Spec and ADR each pointed at the other as confirmation.

Nothing compared the details to the tests, because nothing had to. The issues
under the epic tracked *work items* (delete the paired classes, collapse the
port, rename the misnamed wire classes), not decision details, and an epic with
zero open children looks finished. The Validation section still said the status
"remains `accepted-provisional`", which MS-14-002's marker scan would have
flagged on `status: accepted` — and the graduation commit added
`lint_suppress: [status_prose_contradiction]` to get past it. The suppression
exists for an ADR that legitimately *discusses* provisional-ness; used to clear
a stale sentence it also cleared the one check that asks whether the prose and
the status agree.

Found only because #3888 asked for "which test holds each of the ten details"
and two rows had no honest answer. Resolved by amending details 7 and 8 to what
was built (fail-loudly, federation argument answered via the versioned context
document) and filing #3900 for the envelope, where keys are still dropped.

Claim awaiting a second witness: an ADR graduation should be gated on a
per-detail test map, not on its epic's child count, and a `lint_suppress` added
in the same commit as a status change is a signal to inspect, not a fix.
