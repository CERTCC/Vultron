---
source: NOTES-specs-vs-adrs--provenance-and-forward-only-history
timestamp: '2026-10-14T14:33:13.750047+00:00'
title: 'specs-vs-adrs: provenance notes and forward-only reference check history'
type: note
---

Archived from `notes/specs-vs-adrs.md` by #4498: the source and supersession notes (ISSUE-1777 guidance replaced by ADR-0127, #4389) and the account of #4412 widening the reference shape are history; #4412 delivered MS-15-006. The rules stay in § "An aged code reference in an ADR body is not a defect, and there is no scrub" and § "Routine context routes through records by title and edge".

---

## Removed text

  body.** Cite the ADR for *why*; state the rule where the reader already is.
  MS-11-007 makes this normative for a numbered detail: a citation that names
  one makes the body load-bearing again, and
  `test/metadata/test_no_adr_detail_citations.py` fails any such citation under
  `specs/` or `notes/`. ADR-0099's decision details, the last such citations,
  now live in the ARCH-25 requirement group.

Source: ISSUE-4528 (maintainer review of PR #4538)

### An aged code reference in an ADR body is not a defect, and there is no scrub

This is the consequence most likely to be re-derived as work, so it is stated
outright: the corpus's existing stale code references are **not** a backlog. A
reference in a record's context or validation prose is an accurate account of the
code as it then stood. No issue owns scrubbing them, and no advisory count of
them is reported — a count would re-describe the same sentences as debt and
invite the scrub back. Most of them sit inside a Decision Outcome or Considered
Options section anyway, where the Edit Tiers below would make a rename cost a
dated Amendment.

Enforcement is therefore **forward-only**: a reference newly written into a
record should resolve on the day it is written, which is a question about the
pull request's own diff rather than about the corpus. A merge-blocking check
keyed on code changes is rejected — it would reinstate the refactor obligation
the first bullet above removes. Note that the phantom-symbol half of the
spec-corpus check (MS-15-004) resolves only what `_SPEC_SYMBOL_RE` in
`vultron/metadata/specs/lint.py` matches, which is where to read the live shape.
When #4412 was scoped that was backticked all-caps identifiers with an
underscore, which saw neither a stale class name nor a function name — so a
check extended to record bodies has to widen the shape to be worth anything,
and #4412 is where it widens.

Source: ADR-0127 (`docs/adr/0127-decision-records-leave-routine-agent-context.md`)
and concern #4389. This replaces the ISSUE-1777 guidance (2026-07-31) that
asked authors to revise accepted ADR bodies in place so a reader met only
currently-accurate statements. That pursued the same goal — keeping stale detail
out of a reader's way — through the only mechanism available while every ADR body
was read as routine agent context. Records revised in place under it are left as
they are.
