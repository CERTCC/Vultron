---
title: Issue #1841 and #1843 overlap on StatusAuthorizationCallOutBundle
type: learning
timestamp: 2026-07-30T00:00:00Z
source: ISSUE-1841
signal: process-issue
---

Issue #1841 requires `StatusAuthorizationCallOutBundle` with Seam 1 fields only
(`status_update_guard_factory`). Issue #1843 also asks for `StatusAuthorizationCallOutBundle`
but with both Seam 1 AND Seam 2 fields plus a stochastic singleton
(`STATUS_AUTHORIZATION_STOCHASTIC`).

This PR (#1850) implements the Seam 1 subset as needed by #1841. Issue #1843 should be
updated to note that Seam 1 is already done and to focus on adding Seam 2 fields
(`side_effects_guard_factory`) and the stochastic singleton when Seam 2 work lands.

Alternatively, #1843 could be closed once the Seam 2 issue is created and tracked separately.
