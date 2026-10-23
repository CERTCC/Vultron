---
title: DEMOCI-05-001 push-to-main trigger was specced but not implemented
type: learning
timestamp: 2026-08-06T14:55:00Z
source: ISSUE-1996
signal: process-issue
---

DEMOCI-05-001 requires the demo-integration workflow to run on push events to
main. DEMOCI-06 explicitly depends on it (DEMOCI-06-003 refines DEMOCI-05-001).
However, the `demo-integration.yml` workflow had no `push:` trigger before
PR #2030 — only `pull_request` and `workflow_dispatch`.

Neither the DEMOCI-06 issue body nor the DEMOCI-05 spec entry flagged that
DEMOCI-05-001 was unimplemented. DEMOCI-06 was accepted as a task without this
blocker being surfaced.

The gap was discovered during implementation and the push trigger was added in
the same PR (PR #2030). But DEMOCI-05 should be marked as having an open
implementation gap — or a dedicated task should have been created to implement
the push trigger before DEMOCI-06 was built on top of it.

Action: consider whether DEMOCI-05 needs a follow-up spec verification step
to confirm all DEMOCI-05-001 requirements are now satisfied in the merged workflow.

**Promoted**: 2026-08-17 — captured in process note archived — DEMOCI-05-001 push trigger implemented in PR #2030.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
