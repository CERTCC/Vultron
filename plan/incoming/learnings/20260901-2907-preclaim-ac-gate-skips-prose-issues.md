---
title: "Process gap: the pre-claim AC gate skips prose-format issues, and duplicate #2907/#2908 stayed open"
type: learning
timestamp: 2026-09-01T22:55:00Z
source: ISSUE-2907
signal: process-issue
---

Two tracking failures compounded on #2907.

**1. Duplicate issues, only one closed.** #2907 and #2908 were the same issue,
filed from the same pre-PR code review on #2490, with near-identical titles and
bodies. #2909 fixed most of the work and closed #2908 as COMPLETED with a
comment saying so. #2907 was never cross-referenced, so it sat in the Now-Epic
queue looking like untouched work when seven of its nine declarations were
already done. Nothing in the queue surfaced the duplication — the two issue
numbers are adjacent and the titles differ only in punctuation.

**2. The pre-claim AC gate skipped exactly the case it exists for.**
`.agents/skills/build/SKILL.md` Phase 2 step 6 verifies each `- [ ] AC-N:` item
against `origin/main` before claiming, and explicitly instructs: "If **no**
`- [ ] AC-N:` items are found in the issue body (prose-format or free-form ACs),
skip this gate and proceed directly to step 7." #2907 is prose-format, so the
gate skipped — on an issue that was ~78% already implemented. The gate's own
rationale (AGENTS.md: "Verify Issue ACs Against Current Code Before Starting")
applies regardless of whether the issue author used checkboxes.

Verifying it by hand cost one grep. It also caught the part the gate would have
missed anyway: the issue **body** named four nodes (all four already fixed),
while the **title** covered all `participant_case` ports — two of which were
not. Closing on the body alone would have been wrong.

**Suggested changes**:

- Reword the build skill's gate so a prose-format body means "derive the
  checkable claims from the title and body and verify those", not "skip".
  A summary/title-level claim is verifiable even when no checkbox list exists.
- Add a duplicate check to the gate: before claiming, search closed issues for
  a near-identical title (`gh issue list --state closed --search`). A closed
  twin naming the delivering PR is the strongest possible signal that the open
  one is stale.
- When a review-spawned issue is closed as a duplicate, comment on **both**
  numbers. #2908's closing comment named #2909; #2907 got nothing.

Related: [[20260827-glossary-acs-pre-satisfied]],
[[20260827-issue-1760-adr-already-done]] — the same
already-implemented-but-open pattern, both of which had checkbox ACs and were
therefore caught by the gate.
