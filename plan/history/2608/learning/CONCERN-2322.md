---
source: CONCERN-2322
timestamp: '2026-08-20T15:04:29.610858+00:00'
title: Remove deprecated OFFER_CASE_MANAGER_ROLE and fix ActivityPattern target_ strictness
type: learning
---

## Concern

`OfferCaseManagerRolePattern` silently mis-routes when `_rehydrate_fields`
expansion is skipped. Root cause: `ActivityPattern._match_activity_field`
hardcodes `strict=False` for the `target_` field pair, so a bare URI string
in `target` matches any typed target constraint. This made registry ordering
the **sole** protection against misrouting the deprecated
`Offer(VulnerabilityCase, target=CaseParticipant)` format as an ownership
transfer.

## Decisions

1. **`strict=True` must also gate `target_` matching** — passing `self.strict`
   to the `target_` field pair instead of hardcoded `False` ensures a bare URI
   string cannot match a typed target constraint when `strict=True`.
2. **`OFFER_CASE_MANAGER_ROLE` is removed** (not merely kept deprecated) — the
   wire format was never emitted by any supported actor implementation; retaining
   it as a registry entry was a source of ordering fragility (CONCERN-2322).
3. **`ACCEPT_CASE_PARTICIPANT_ROLE` and `REJECT_CASE_PARTICIPANT_ROLE`** are
   added to complete the three-way role-offer flow for the canonical
   `OFFER_CASE_PARTICIPANT_ROLE` format.

## Scope of removal

~61 production code locations across ~15 files plus ~99 test locations spanning:
wire patterns, semantic registry, BT nodes (`SendOfferCaseManagerRoleNode`,
`AutoAcceptCaseManagerRoleNode`, `EmitRejectCaseManagerRoleNode`), BT trees,
trigger factories, ports, adapters, FastAPI endpoint, and demo test assertions.

`case_participant_role.py` (new format's received-use-case) currently borrows
the old `offer_case_manager_role_received_tree` — a new dedicated tree must be
built before the old one can be deleted.

## Docs changes

- `specs/semantic-extraction.yaml`: SE-08-001/002 rationales made generic;
  SE-08-004 added (strict=True for target_ discriminators); SE-08-005 added
  (documents removal, replaces old SE-08-004 deprecation entry)
- `docs/adr/0039-offer-case-participant-role-wire-type.md`: amendment section
  added documenting the strictness fix and removal decision
- `notes/activitystreams-state-update.md`: Target-Field Discriminators section
  updated to reflect removal and strict=True fix
- `AGENTS.md`: stale ordering pitfall replaced with target_ permissiveness
  pitfall (SE-08-004, CONCERN-2322)

## Implementation issues

- #2428 (size:S) — Wire strictness fix + AcceptCaseParticipantRolePattern +
  RejectCaseParticipantRolePattern + registry entries
- #2429 (size:L) — Full removal of OFFER_CASE_MANAGER_ROLE from all layers +
  new received-tree for OFFER_CASE_PARTICIPANT_ROLE

## Reference

PR: <https://github.com/CERTCC/Vultron/pull/2427>
