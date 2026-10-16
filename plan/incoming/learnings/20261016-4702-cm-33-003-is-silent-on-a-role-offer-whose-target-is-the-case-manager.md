---
title: "CM-33-003 is silent on a role Offer whose target is the case's CASE_MANAGER, which the forward cannot serve"
type: learning
timestamp: "2026-10-16T16:30:00Z"
source: ISSUE-4702
signal: spec-gap
---

**Trigger.** You change which role Offers the CASE_MANAGER admits, or you
build the CASE_MANAGER-originated Offer that CM-33-002 permits.

**Claim.** CM-33-003 lists the role Offers the CASE_MANAGER refuses (no
readable role, `CASE_OWNER`, `CASE_MANAGER`, a non-participant target, a held
role) but says nothing about an Offer whose target is the CASE_MANAGER itself.
CM-33-001 then has the CASE_MANAGER forward the Offer to the target, an emit
whose only recipient is the executing actor, which BT-17-008 forbids, and
CM-33-004 has the target answer the CASE_MANAGER, so the answer would go to
itself.

**Evidence.** PR #4813 refuses such an Offer in `RoleOfferAdmissibleNode`
(`vultron/core/behaviors/case/nodes/role_offer_guard.py`), citing BT-17-008,
and pins it with `test_offer_naming_the_case_manager_as_target_is_refused`.
The refusal is a reading of BT-17-008, not a CM-33 requirement.

**Proposed resolution.** Add the case to CM-33-003 (refuse it), or specify how
the CASE_MANAGER answers an Offer made to itself without a self-addressed
forward.
