---
title: A reverted "symptom-only" fix can still be the correct fix once the root cause is removed
type: learning
timestamp: "2026-07-30T22:10:00+00:00"
source: ISSUE-1777-c
signal: spec-ambiguity
---

Commit `256ef3e1` added `("Add", "CaseStatus")` to `_CASE_AUTHORED_SIGNATURES`;
commit `f6578c22` reverted it, and ADR-0041 lists it as option 3, "symptom
fix". Reading only that history suggests the entry must stay absent. But
CLP-12-001 is a MUST *requiring* its presence, and #1767's ACs depend on it.

**Why:** The revert rejected the entry as a *substitute* for removing the
vendor-authored back-fill, not as a change that was wrong in itself. Once the
back-fill is gone and the CaseActor authors those entries natively (CM-22-003),
the signature entry is exactly what CLP-12-001/CLP-12-002 demand. The
"symptom-only" label was about sequencing, not correctness.

**How to apply:** When git history shows a change was reverted, check whether it
was reverted for being *wrong* or for being *premature*. Read the governing spec
item's priority before inheriting the revert's conclusion — a MUST in the spec
corpus outranks an inference from a commit message. Note the revert's reasoning
in the notes file alongside the eventual re-application so the next reader sees
both halves.

**Promoted**: 2026-07-31 — captured in `notes/bt-pitfalls.md` (reverted symptom-only fix section).
Docs PR: TBD.
