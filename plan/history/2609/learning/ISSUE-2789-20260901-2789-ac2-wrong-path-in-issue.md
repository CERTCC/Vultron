---
title: "ISSUE-2789 AC-2 named a path that would have duplicated an existing scenario"
type: learning
timestamp: "2026-09-01T00:00:00Z"
source: ISSUE-2789
signal: process-issue
---

## The decision

ISSUE-2789 AC-2 asked for `vultron/demo/exchange/fvcv_handoff_demo.py` to be
created, stating the file "does not exist yet". A full FVCV-handoff scenario
already exists at **`vultron/demo/scenario/fvcv_handoff_demo.py`** — 1300+ lines,
wired into the demo CLI, the Docker topology and the Demo Integration CI matrix.
`notes/ownership-transfer.md` has cited that path since ADR-0053 was written.

Creating the file AC-2 literally names would have produced a second FVCV-handoff
demo in the wrong package: `exchange/` holds single-exchange demos against one
container, `scenario/` holds multi-container end-to-end scenarios. So the issue's
path was stale, not the requirement.

Judgment call made unattended: treat AC-2 as satisfied by the existing scenario
and close its one genuine gap instead — the scenario never asserted ADR-0053's
own validation criterion (the Finder learning of the completed transfer from
`Announce(CaseLedgerEntry)`). Added as a `demo_check` in
`_phase_ownership_handoff`, plus a unit assertion that the wait is performed on
the Finder's own container rather than the offerer's.

## How to apply

When an issue body names a path, check whether the *capability* exists elsewhere
before creating the file. An issue written before a scenario landed will name a
plausible-but-wrong location, and "the file does not exist" is a claim about the
path, not about the behaviour. Grep for the bare filename across the repo —
`notes/` cross-references are the fastest tell, since they track the real path.

Related: the AC-4 clause "new integration test verifies Finder notification via
ledger broadcast" was likewise already delivered, as
`TestOwnershipTransferAnnounceReachesFinderAC5c` in
`test/demo/test_fvcv_handoff_demo.py` (commit `36a7ba97c`).

---

**Promoted**: 2026-09-03 — captured in `notes/git-workflow-pitfalls.md` ("An Issue That Names a Missing File Is Making a Claim About the Path, Not the Behaviour"). Docs PR: <https://github.com/CERTCC/Vultron/pull/3147>.
