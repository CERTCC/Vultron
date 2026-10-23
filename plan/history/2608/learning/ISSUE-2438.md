---
title: Duplicate issue — #2438 duplicated already-in-flight #2184
type: learning
timestamp: "2026-08-25T00:00:00Z"
source: ISSUE-2438
signal: process-issue
---

Issue #2438 ("Implement notify-failure composite action and wire all qualifying CI workflows") was fully implemented by PR #2612 (issue #2184, "Implement CI failure alerting: notify-failure composite action, workflow wiring, and spec test"), which merged to `main` while #2438 was still being worked. Both issues described the same deliverables: the composite action, 7 qualifying workflows wired, labels, and CISEC-05-004 test coverage.

The duplicate was discovered only when `freshen-branch.sh` produced add/add and content conflicts in all 8 workflow files, which surfaced the parallel merge.

**Root cause**: Two issues describing the same feature were open simultaneously — #2184 (created earlier, broader title) and #2438 (created later, more specific title) — with no `blockedBy` or `duplicates` link between them. A pre-claim dedup check against open issues with overlapping keywords (e.g. "notify-failure", "CI failure alerting") could have caught this before branching.

**Suggestion**: Before claiming an issue, scan open issues for keyword overlap with the title. If a recent match is found, verify whether the work is already in flight before branching.

**Promoted**: 2026-08-27 — archived (already in specs/notes/AGENTS.md or tracked as GitHub issue). Docs PR: <pending>.
