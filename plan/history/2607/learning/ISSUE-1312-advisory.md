---
title: "AdvisoryReviewDecision.approved field is informational, not a pipeline gate"
type: learning
timestamp: "2026-07-22T00:00:00Z"
source: ISSUE-1312-advisory
signal: design-question
---

The `AdvisoryReviewDecision` model has an `approved: bool = True` field that
was initially documented as "permits submission to the advisory platform".
At implementation time the pre-PR code review flagged this as a
documentation-code inconsistency: the pipeline never reads `approved`; only
`needs_revision` is read (by `_NeedsRevisionGate`).

Decision made: `approved` is metadata for the `ReviewAdvisoryDraft` backend
to record its decision. A backend that needs to block submission without
requesting edits (e.g. legal hold) MUST return `Status.FAILURE` from
`update()` so the Sequence fails. Gating on `approved=False` is deferred
to a follow-on design question (see AC-4 in issue #1312).

The docstring in `publish_artifact_tree.py` was updated to reflect this
before the PR landed. A future issue should decide whether an explicit
`approved=False` guard should be added to the pipeline, or whether the
convention of returning FAILURE from the Evaluator is sufficient.

**Promoted**: 2026-07-28 — deferred design question tracked as ISSUE-1783.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1790>0>0>0>0>0>0>.
