---
title: "OfferCaseManagerRolePattern permissive string target is a silent mis-route risk"
type: learning
timestamp: "2026-08-11T00:00:00Z"
source: ISSUE-2194-permissive-target
signal: concern
---

`OfferCaseManagerRolePattern` uses `target_=VOtype.CASE_PARTICIPANT` but
`ActivityPattern._match_activity_field` treats bare string URIs as
"permissively allowed" for `target_`.  This means any
`Offer(VulnerabilityCase)` with a string `target` matches the case-manager-role
pattern, which precedes `OfferCaseOwnershipTransferActivityPattern` in the
registry (SE-08-001 ordering).

Correct routing therefore depends on `_rehydrate_fields` expanding the
`target` string to its typed domain object (e.g. as_Organization) BEFORE
pattern matching runs.  If that expansion is skipped (e.g. because the
object is kept inline), the dispatcher silently selects the wrong use case.

Consider: (a) adding a `target_strict` per-field flag to `ActivityPattern`
so CASE_PARTICIPANT matching rejects strings, or (b) reordering registry
entries so ownership-transfer appears before case-manager-role and does NOT
require target discrimination.  File as a Concern issue.

**Promoted**: 2026-08-17 — captured in GitHub #2322 (Concern: OfferCaseManagerRolePattern silently mis-routes).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.
