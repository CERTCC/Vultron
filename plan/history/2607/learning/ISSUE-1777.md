---
title: An ADR "what is removed" list can name a component that spec MUSTs still require
type: learning
timestamp: "2026-07-30T22:00:00+00:00"
source: ISSUE-1777
signal: spec-contradiction
---

ADR-0041's "What is removed" section lists `SendOfferCaseManagerRoleNode` and
`WritePrologueLedgerEntriesNode` together, and Issue #1777 AC-2 says the
`Offer(CaseManagerRole)` accept/reject path should be "removed or reduced to a
no-op stub". But DEMOMA-08-002, DEMOMA-08-003, and DEMOMA-08-006 through
DEMOMA-08-009 are MUSTs describing that handshake as a protocol operation in its
own right (explicit CASE_MANAGER delegation to a service actor while the vendor
retains CASE_OWNER), and `offer_case_manager_role_trigger_bt` in
`actor_trigger_trees.py` is a live manual-trigger surface for it.

**Why:** The ADR was reasoning about one *use* of the component — its role in
case initialization — not about the component's whole existence. Reading the
removal list literally would have deleted a spec-mandated capability and
silently dropped inbound `Offer(CaseManagerRole)` traffic from pre-ADR-0041
actors.

**How to apply:** When an ADR lists a node/module for removal, grep the spec
corpus for the *operation* that node implements before deleting it, and check
`actor_trigger_trees.py` for a manual-trigger entry point. If MUST-level specs
still require the operation, remove only the coupling the ADR actually
supersedes, keep the component functional, and record the narrowed scope in the
module docstring so the next reader does not re-litigate it. See
[[feedback_completeness_doctrine]].

**Resolved:** ADR-0041 was revised in PR #1851 to scope both the
`Offer(CaseManagerRole)` and `CreateCaseActorNode` removal entries to the
report-receipt path, so the conflict no longer exists in the document. The
detection habit above is still the transferable part. On the choice to revise
rather than append an amendment, see
[[20260731-revise-recent-adrs-not-amend]].

**Promoted**: 2026-07-31 — captured in `AGENTS.md` (ADR "what is removed" lists are scoped section).
Docs PR: TBD.
