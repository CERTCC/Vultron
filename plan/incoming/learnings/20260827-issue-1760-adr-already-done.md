---
title: Issue 1760 — ADR section already present; only spec entry was missing
type: learning
timestamp: 2026-08-27
source: ISSUE-1760
signal: process-issue
---

Issue #1760 stated that ADR-0026 "does not document" the trust invariant for
roles coming from the stored Offer rather than the received Accept. In practice,
the ADR already had the full "Trust Rule: Roles Come From the Offer, Not the
Accept" section — it was added in commit f415f83a ("docs: promote learnings —
spec gaps, pitfalls, notes, and bug fix") on 2026-07-28.

The actual gap was the missing normative spec entry in specs/case-management.yaml,
which this PR (2743) adds as CM-16-018.

**Lesson**: when an issue references both a doc file and a spec file, verify each
independently before branching. The pre-claim AC verification gate in build Phase
2 skips when there are no formal `- [ ] AC-N:` items, so free-form issues with
prose requirements need a manual check of each named artifact.
