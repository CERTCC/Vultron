---
title: "A pin-to-live-count ratchet races every PR in flight when it lands — the first post-merge main is red through no PR's own fault"
type: learning
timestamp: "2026-09-30T19:40:00Z"
source: ISSUE-3828
signal: theme-candidate
---

While validating #3828 (a test-only PR that touches nothing under `specs/`),
the freshened branch failed
`test/metadata/specs/test_must_verification_ratchet.py::test_live_unverified_counts_equal_their_ceilings`
(MS-10-006): project-kind ceiling 1004, live count 1003. The test reads only
the spec corpus, so the PR could not have moved it; `main` itself was red on
the same assertion (auto-filed #3970 and #3966).

The mechanism: #3942 landed a *two-directional* ratchet (below the ceiling
fails too, so a backfill must lower the ceiling in the same PR). #3941 was in
flight at the time and added `verification:` to project-kind specs in
`specs/case-ledger-processing.yaml`. Each PR was green against the `main` it
was built on; their union was red. A one-sided ratchet cannot fail this way
(that is the slack #3959 and #3931 complain about), so the two properties
trade off: the two-sided pin catches silent slack but turns every concurrent
backfill into a `main` break that no PR's CI could have shown.

Claim, unproven from one instance: a ratchet that pins a count in both
directions needs one of (a) a merge-queue or post-merge re-check on `main`
that auto-lowers, (b) a "below" arm that reports and files rather than
fails, or (c) an explicit "land it alone, re-measure at merge" step in the PR
that introduces it. Seen once; a second two-sided ratchet landing red would
corroborate it.

**Promoted**: 2026-10-02 — Already closed — tracked by Concern #3984.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4174>.
