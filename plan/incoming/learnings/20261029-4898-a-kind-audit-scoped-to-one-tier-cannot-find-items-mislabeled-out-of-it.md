---
title: "A kind audit that re-checks only the protocol tier cannot find protocol rules mislabeled as project"
type: learning
timestamp: "2026-10-29T00:00:00Z"
source: ISSUE-4898
signal: theme-candidate
---

**Trigger.** You rely on the MS-12 kind re-audit (#4889 to #4894) to trust that
every rule the Protocol Specification needs is `protocol` or `foundation`.

**Claim.** That audit re-checked the items that were already `protocol` or
`foundation`. It skipped the items that were already `project` or
`architecture`, so it cannot have found a protocol rule labeled `project`.
Mislabeling in that direction shows up only when a page reconcile tries to
render the rule as a callout and the build refuses it.

**Evidence.** The Case Tracking Models reconcile found four such rules:
CM-18-003 (the consent-row trigger table), MSM-07-008, MSM-07-009 and
MSM-07-010 (the owner's activate and reject decisions, and `Leave(EmbargoEvent)`).
The kind PRs listed MSM-07 and EMB-18 as "already project or architecture,
outside the protocol/foundation slice". All four are state-machine and
receiver behavior under MS-12-003. #4898 relabeled them.

**Corroboration to look for.** The remaining reconciles (#4899, #4900) find
more `project` items that every implementation must obey. If they do, an audit
of the `project` items that name a wire activity or a state-machine trigger
is due.
