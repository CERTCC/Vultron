---
source: NOTES-datalayer-design--audited-core-activity-read-back-sites
timestamp: '2026-10-12T19:32:57.524747+00:00'
title: 'Audited core activity read-back sites (concern #1506)'
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered — the concern #1506 audit is closed and every category A/B site has migrated; categories C and D need no change.
**Superseded by:** DL-06 in `specs/datalayer.yaml`; ADR-0035; `notes/datalayer-design.md` § "Activity Read-Back"

---

## Audited core activity read-back sites (concern #1506)

Classification of every `dl.read(activity_id)` / activity `list_objects()` site
in `vultron/core/` at audit time. Categories A/B need migration; C is the
sanctioned seam; D is not an activity read (covered by DL-05 / #1503).

**A — plumbing re-reads** (re-read only to `model_dump()` the just-emitted
activity into the API response; the factory already built the object):

- `vultron/core/use_cases/triggers/report.py` — `_handle_result` in
  `SvcValidateReportUseCase`, `SvcInvalidateReportUseCase`, `SvcRejectReportUseCase`,
  `SvcCloseReportUseCase` (4 sites).
- ~~`vultron/core/behaviors/case/nodes/delegation.py`~~ — `CreateOfferCaseManagerActivityNode`
  re-read the just-created `Offer(CaseManagerRole)`. Deleted in issue #2429 when
  `OFFER_CASE_MANAGER_ROLE` infrastructure was removed (ADR-0039).
- *Fix*: `TriggerActivityPort` returns `(activity_id, activity_dict)`; delete the
  re-reads. Not even a semantic read.

**B — semantic-content reads** (core re-interprets a stored activity for a
domain fact — the ARCH-09-001 core violations):

- ~~*report/offer*~~: migrated (#1518). `VultronOfferRecord` now captures
  offer facts at adapter time (sender) and received-side ingest time (receiver).
  Core reads `VultronOfferRecord` instead of the stored wire `Offer` activity.
- ~~*embargo*~~: migrated (#1519). `pending_embargo_proposal_index: dict[str,
  str]` (embargo_id → proposal_id) added to `VulnerabilityCase`; populated on
  receive (`InviteToEmbargoOnCaseReceivedUseCase`) and trigger
  (`SvcProposeEmbargoUseCase._handle_result`). All `dl.read(invite_id)` and
  `list_objects("Invite")` semantic reads in `received/embargo/`,
  `triggers/_helpers.py`, and `dispatcher.py` removed. `Invite` removed from
  DL-05-004 exemptions.
- ~~*actor/participant*~~: migrated (#1520). `recommendation_recommender_index:
  dict[str, str]` (recommendation_id → recommender_actor_id) added to
  `VulnerabilityCase`; populated in `OfferActorToCaseReceivedUseCase.execute()`.
  `AcceptOfferCaseParticipantReceivedUseCase` and
  `RejectOfferCaseParticipantReceivedUseCase` now read
  `case.recommendation_recommender_index.get(recommendation_id)` instead of
  `dl.read(recommendation_id)`. Redundant `invite_type != "Invite"` check
  removed from `SvcAcceptCaseInviteUseCase._prepare()`.
- *Fix*: capture the fact as core state at extraction time; read it from core.

**C — envelope reconstitution** (verbatim original needed for a reply):

Audited by #1521. Four live reply paths need the verbatim original activity
inline in the reply's `object_`:

- `TriggerActivityAdapter.accept_case_invite` (`actors.py`) — reads the
  stored `Invite` and passes it verbatim to `rm_accept_invite_to_case_activity`.
- `TriggerActivityAdapter.accept_embargo` (`embargo.py`) — reads the stored
  embargo proposal `Invite` and passes it to `em_accept_embargo_activity`.
- `TriggerActivityAdapter.reject_embargo` (`embargo.py`) — same pattern for
  `em_reject_embargo_activity`.
- `TriggerActivityAdapter.accept_case_participant_offer` (`actors.py`) —
  reads the stored `Offer(CaseParticipant)` and passes it to
  `accept_case_participant_offer_activity`.

**All four reads are already in the adapter layer** (`vultron/adapters/driven/
trigger_activity_adapter/`), not in `vultron/core/`. They satisfy DL-06-004:
the payload is treated opaquely (passed straight to the factory without any
semantic interpretation). No new seam is needed; the correct seam already
exists. The DL-05-004 exemption set does not need modification for these sites
because they are not core reads.

Tests verifying verbatim reconstitution (id preserved in `in_reply_to` /
`object.id`) are in `test/adapters/driven/trigger_activity_adapter/`.

**D — not activities** (core entities, covered by DL-05 / #1503, out of scope):

- `dispatcher.py:147` (`VultronReplicationState`); `received/actor/announce.py:29`
  (`VultronReportCaseLink`); `list_objects("CaseLedgerEntry")` reads; case /
  participant / status / marker reads.

Implementation is tracked in the issues filed from concern #1506 (blocked by
that concern, children of Epic #1394). As each B site migrates, remove its
Activity type from the DL-05-004 exemption set (DL-06-005) until the set reaches
zero.
