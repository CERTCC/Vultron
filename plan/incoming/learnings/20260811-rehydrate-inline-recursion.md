---
title: "_rehydrate_fields must recurse into inline BaseModel objects"
type: learning
timestamp: "2026-08-11"
source: ISSUE-2194
signal: design-question
---

When `_KEEP_INLINE_NESTED_TYPES` keeps an Activity (e.g. Offer) inline in a
stored parent Activity (e.g. Accept), the inline object arrives at
`_rehydrate_fields` as a `BaseModel` instance, not a bare string.  The old
`_rehydrate_fields` only expanded string ID references, so the nested object's
own reference fields (e.g. `target`) were never expanded from the DataLayer.

Decision: extend `_rehydrate_fields` to recurse into inline `BaseModel` values
found in `_AS_OBJECT_REF_FIELDS` slots, so the full expansion chain mirrors
what previously happened via the dehydrate-then-read-back-separately path.

Without this recursion, `target` remained a bare URI string.  Pattern
matching in `OfferCaseManagerRolePattern` is permissive for strings, so the
wrong semantics (`accept_case_manager_role`) were matched instead of
`accept_case_ownership_transfer`, silently mis-routing the Accept.

**Promoted**: 2026-08-17 — captured in GitHub #2322 (Concern: OfferCaseManagerRolePattern silently mis-routes).
Docs PR: TBD.
