---
source: ISSUE-2416,ISSUE-2417
timestamp: '2026-08-20T14:05:15.991294+00:00'
title: guard CORE_TYPE_MAP against wire types; document two-registry model
type: implementation
---

Issues #2416 and #2417 batched. PR: <https://github.com/CERTCC/Vultron/pull/2424>

## #2416 — wire types contaminating CORE_TYPE_MAP

Symptom: importing any wire vocabulary type (e.g. `as_CaseLedgerEntry`) caused 74+ wire types (`as_Accept`, `as_Create`, `as_Activity`, etc.) to self-register in `CORE_TYPE_MAP`, contradicting the module docstring ("catches non-CoreObject core types") and creating a maintenance hazard.

Root cause: `VultronObject.__init_subclass__` fires for ALL `VultronObject` subclasses including wire-layer `as_Object` descendants. No branch guard existed to distinguish core from wire subclasses at registration time.

Fix: Added `_is_core_branch: ClassVar[bool] = True` sentinel to `VultronObject` (default: assume core branch). Overrode it to `False` on `as_Object` (propagates to all wire subclasses via inheritance). Added `if not cls._is_core_branch: return` guard at the top of `VultronObject.__init_subclass__`.

## #2417 — ARCH-12-004 spec did not document the two-registry model

Symptom: ARCH-12-004 stated "core-branch types MUST register in `CORE_VOCABULARY`" but five `VultronObject`-direct types (`VultronOfferRecord`, `VultronPendingCaseInbox`, `PendingCreateCaseActivity`, `VultronReplicationState`, `VultronReportCaseLink`) correctly register in `CORE_TYPE_MAP`, not `CORE_VOCABULARY`. Investigation found `CORE_VOCABULARY` is the DataLayer primary path (must be `CoreObject` subclasses only; enforced by existing test). `CORE_TYPE_MAP` is the wire-layer fallback path. Both roles are legitimate and distinct.

Root cause: ARCH-12-004 was written before the two-registry model was introduced (PR #2410, ISSUE-1992). The spec was never updated.

Fix: Updated ARCH-12-004 in `specs/architecture.yaml` to document the two-registry model with rationale. Option 2 (update spec) chosen over Option 3 (retire CORE_VOCABULARY) because `CORE_VOCABULARY` serves the distinct DataLayer primary reconstruction role and retiring it would break `_from_row()`.
