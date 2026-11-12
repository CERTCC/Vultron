#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Every trigger-port activity is sealed complete (#2655 AC-1, VM-08-003).

One recipe per ``TriggerActivityPort`` method that produces an outbound
activity.  For each, the adapter must:

- seal the body it returns to core (or, for id-only methods, seal a body for
  the id it returns), so the outbox has something to relay;
- put a fully inline ``object`` on every initiating activity (AKM-03-003) —
  the outbox no longer expands a bare reference at delivery time, so a factory
  that emitted one would now be refused rather than repaired — except that a
  ``Join``, ``Ignore``, ``Leave`` or ``Offer`` of a case names the case by
  its typed reference and carries no copy of it, at any depth (AKM-03-004);
- address the recipients it was given;
- carry a case in ``target`` only as its URI or the selective-disclosure stub
  (MV-10-001), since nothing downstream collapses it any more.

The recipe table is a ratchet: a port method with no recipe fails the test, so
a new outbound activity cannot be added without being audited here.
"""

import inspect
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from test.support.future_dates import days_from_now
from test.support.objects import authored_at, make
from test.support.received import archive_delivered
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.driving.fastapi.outbox_delivery import (
    _INLINE_OBJECT_ACTIVITY_TYPES,
)
from vultron.adapters.outbox_sealed_body import (
    dump_outbound_body,
    read_sealed_body,
)
from vultron.core.models.activity import VultronCreateCaseActivity
from vultron.core.models.case_naming import CASE_NAMING_ACTIVITY_TYPES
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.vulnerability_item import VulnerabilityItem
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.examples.status import (
    add_fix_readiness_to_participant,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    is_case_reference_shape,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_ACTOR = "https://example.org/actors/coordinator"
_PEER = "https://example.org/actors/vendor"
_CASE_ACTOR = "https://example.org/actors/case-actor"
#: The act an ``Update`` record follows (an accepted ownership-transfer Offer).
_CAUSE_ID = "https://example.org/activities/accepted-offer"

#: Ledger records that carry the case as stored, its participants and reports
#: by id: each of those has an entry of its own, so a replica copying the
#: record holds the case as the CASE_MANAGER does (ADR-0124).  A record is no
#: message, so it seeds no recipient (CBT-01-007 does not apply).  The genesis
#: record is not one: it is the creation's delivered ``Create`` (ADR-0157).
_CASE_AS_STORED = frozenset({"record_case_owner_updated"})

#: Port methods that build a domain *object*, not an outbound activity, or
#: (``add_object_to_case_semantics``) classify one without persisting it.
_NOT_AN_ACTIVITY = frozenset(
    {
        "create_note",
        "requeue_embargo_refusal",
        "answered_embargo_invite",
        "add_object_to_case_semantics",
        # The ReceivedActivityLoader half of the port loads; it builds no
        # activity (ADR-0149).
        "load_received_activity",
    }
)


class _World:
    """One seeded store per actor, and the ids the recipes need.

    An outbox signs only its own actor's activities (SIG-05-004), so each
    recipe sends through the store of the actor it sends as
    (:meth:`adapter_as`).  Every store holds the same seeded objects, and an
    activity one actor sends that another answers is delivered to the
    answerer's store, as its inbox would archive it.
    """

    def __init__(self) -> None:
        self._stores: dict[str, SqliteDataLayer] = {}
        self.case_id: str = "https://example.org/cases/audit-case"
        self.vendor = make(as_Service, id_=_PEER, name="Vendor")
        self.report = make(
            as_VulnerabilityReport, name="CVE-2026-1", content="PoC"
        )
        self.participant = make(
            as_CaseParticipant, context=self.case_id, attributed_to=_PEER
        )
        # The case names its participant and report by id, as a stored case
        # does; a case put on the wire carries them inline: the participant
        # because its receiver cannot hold it (CBT-01-007), the report because
        # this prototype carries every report its sender holds (AKM-02-004).
        self.case = make(
            as_VulnerabilityCase,
            id_=self.case_id,
            name="CVE-2026-1",
            stub_summary="Test case — RCE in widget",
            attributed_to=_ACTOR,
            case_participants=[str(self.participant.id_)],
            vulnerability_reports=[str(self.report.id_)],
        )
        self.status = make(ParticipantStatus, context=self.case_id)
        self.embargo = make(
            as_EmbargoEvent, context=self.case_id, end_time=days_from_now(45)
        )
        self.dl = self.store(_ACTOR)
        self.adapter = self.adapter_as(_ACTOR)
        note_id, _ = self.adapter.create_note(
            name="n",
            content="c",
            context_id=self.case_id,
            attributed_to=_ACTOR,
            at=authored_at(),
        )
        self.note_id = note_id

    def store(self, actor_id: str) -> SqliteDataLayer:
        """*actor_id*'s own store, seeded on first use."""
        if actor_id not in self._stores:
            dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
            self._stores[actor_id] = dl
            for seeded in (
                self.vendor,
                self.report,
                self.participant,
                self.case,
                self.status,
                self.embargo,
            ):
                dl.create(seeded)
            if actor_id != _ACTOR:
                note = self.dl.read(self.note_id, raise_on_missing=True)
                assert note is not None
                dl.create(note)
        return self._stores[actor_id]

    def adapter_as(self, actor_id: str) -> TriggerActivityAdapter:
        """The adapter over *actor_id*'s own store: it sends as that actor."""
        return TriggerActivityAdapter(self.store(actor_id))

    def sealed_by(self, activity_id: str) -> tuple[SqliteDataLayer, Any]:
        """The one store that sealed *activity_id*, and its sealed body."""
        found = [
            (dl, sealed)
            for dl in self._stores.values()
            if (sealed := read_sealed_body(dl, activity_id)) is not None
        ]
        assert len(found) == 1, (
            f"{activity_id} sealed in {len(found)} stores, not one"
        )
        return found[0]

    def deliver(self, sender: str, activity_id: str, holder: str) -> None:
        """Archive *sender*'s sealed *activity_id* in *holder*'s store."""
        sealed = read_sealed_body(self.store(sender), activity_id)
        assert sealed is not None
        archive_delivered(self.store(holder), sealed.body)

    def close(self) -> None:
        for dl in self._stores.values():
            dl.clear_all()
            dl.close()

    def consent_row(self, state: EmbargoConsentState) -> EmbargoConsent:
        """The participant's consent row for the seeded embargo."""
        return EmbargoConsent(
            embargo_id=str(self.embargo.id_),
            state=state,
            attributed_to=_PEER,
        )

    # -- prerequisites other recipes build on ----------------------------------

    def offer_id(self, holder: str = _ACTOR) -> str:
        """The finder's report Offer, as *holder* received it."""
        offer_id, _ = self.adapter_as(_PEER).submit_report(
            report_id=str(self.report.id_),
            actor=_PEER,
            to=_ACTOR,
            target=_ACTOR,
            at=authored_at(),
        )
        self.deliver(_PEER, offer_id, holder)
        return offer_id

    def invite_id(self) -> str:
        """An Invite as the invitee holds it: archived by intake (CLP-10-017)."""
        invite_id, _ = self.adapter.invite_actor_to_case(
            invitee_id=_PEER,
            case_id=self.case_id,
            actor=_ACTOR,
            to=[_PEER],
            at=authored_at(),
        )
        self.deliver(_ACTOR, invite_id, _PEER)
        return invite_id

    def full_case_invite_id(self) -> str:
        """A full-case Invite as the invitee holds it (archived by intake)."""
        invite_id, _ = self.adapter.invite_actor_to_full_case(
            invitee_id=_PEER,
            case_id=self.case_id,
            actor=_ACTOR,
            to=[_PEER],
            ledger_log_index=3,
            ledger_entry_hash="ab" * 32,
            at=authored_at(),
        )
        self.deliver(_ACTOR, invite_id, _PEER)
        return invite_id

    def recommendation_id(self) -> str:
        """The peer's recommendation, as the coordinator received it."""
        rec_id, _ = self.adapter_as(_PEER).suggest_actor_to_case(
            recommended_id=_PEER,
            case_id=self.case_id,
            actor=_PEER,
            to=[_ACTOR],
            at=authored_at(),
        )
        self.deliver(_PEER, rec_id, _ACTOR)
        return rec_id

    def cp_offer_id(self) -> str:
        cp_id, body = self.adapter.offer_actor_to_case(
            recommender_id=_PEER,
            recommended_id=_PEER,
            case_id=self.case_id,
            actor=_ACTOR,
            origin=self.recommendation_id(),
            to=[_ACTOR],
            at=authored_at(),
        )
        # The CASE_MANAGER answers the Offer it received, as the body that
        # was delivered (DL-06-006, ADR-0149).
        archive_delivered(self.dl, body)
        return cp_id

    def proposal_id(self, holder: str = _ACTOR) -> str:
        """The coordinator's embargo Invite, as *holder* holds it."""
        proposal_id, _ = self.adapter.propose_embargo(
            embargo_id=str(self.embargo.id_),
            case_id=self.case_id,
            actor=_ACTOR,
            to=[_PEER],
            at=authored_at(),
        )
        if holder != _ACTOR:
            self.deliver(_ACTOR, proposal_id, holder)
        return proposal_id

    def case_proposal(self) -> dict[str, Any]:
        _, blob = self.adapter_as(_PEER).create_case_proposal(
            actor=_PEER,
            report_id=str(self.report.id_),
            case_actor_id=_CASE_ACTOR,
            to=[_CASE_ACTOR],
            at=authored_at(),
        )
        proposal = json.loads(blob)["object"]
        assert isinstance(proposal, dict)
        return proposal

    def ownership_offer_id(self) -> str:
        """The CASE_MANAGER's Offer as the transferee holds it (archived)."""
        offer_id, blob = self.adapter.offer_case_ownership_transfer(
            case_id=self.case_id,
            transferee_id=_PEER,
            actor=_ACTOR,
            to=[_PEER],
            at=authored_at(),
        )
        # The transferee answers the Offer it received, as delivered
        # (DL-06-006, ADR-0148).
        archive_delivered(self.store(_PEER), blob)
        return offer_id

    def ownership_proposal_id(self) -> str:
        proposal_id, _ = self.adapter.propose_case_ownership_transfer(
            case_id=self.case_id,
            transferee_id=_PEER,
            actor=_ACTOR,
            to=[_CASE_ACTOR],
            at=authored_at(),
        )
        return proposal_id

    def prepared_create_case(self) -> dict[str, Any]:
        # Mirrors ``EmitCreateVulnerabilityCaseNode._build_case_object``: the
        # prepared payload carries the participants (ADR-0041 AC-5, CP-09-004)
        # and the reports it holds (AKM-02-004) as objects; the adapter
        # persists it unchanged (CP-05-005), so the audit hands it the shape
        # production does.
        stored = self.store(_CASE_ACTOR).read(
            self.case_id, raise_on_missing=True
        )
        assert stored is not None
        # The case rides on the activity and the whole graph renders once
        # (VM-10-005, #6046).
        return As2WireRenderAdapter().render(
            make(
                VultronCreateCaseActivity,
                actor=_CASE_ACTOR,
                object_=stored.model_copy(
                    update={
                        "case_participants": [self.participant],
                        "vulnerability_reports": [self.report],
                    }
                ),
                context=self.case_id,
                to=[_PEER],
            )
        )


Recipe = Callable[[_World], Any]

RECIPES: dict[str, Recipe] = {
    # notes
    "add_note_to_case": lambda w: w.adapter.add_note_to_case(
        note_id=w.note_id,
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        at=authored_at(),
    ),
    # reports
    "submit_report": lambda w: w.adapter_as(_PEER).submit_report(
        report_id=str(w.report.id_),
        actor=_PEER,
        to=_ACTOR,
        target=_ACTOR,
        at=authored_at(),
    ),
    "validate_report": lambda w: w.adapter.validate_report(
        offer_id=w.offer_id(),
        report_id=str(w.report.id_),
        actor=_ACTOR,
        to=[_PEER],
        at=authored_at(),
    ),
    "close_report": lambda w: w.adapter.close_report(
        offer_id=w.offer_id(),
        report_id=str(w.report.id_),
        actor=_ACTOR,
        to=[_PEER],
        at=authored_at(),
    ),
    "invalidate_report": lambda w: w.adapter.invalidate_report(
        offer_id=w.offer_id(), actor=_ACTOR, to=[_PEER], at=authored_at()
    ),
    "ack_report": lambda w: w.adapter.ack_report(
        offer_id=w.offer_id(), actor=_ACTOR, to=[_PEER], at=authored_at()
    ),
    # cases
    "create_case": lambda w: w.adapter.create_case(
        case_id=w.case_id, actor=_ACTOR, to=[_PEER], at=authored_at()
    ),
    "engage_case": lambda w: w.adapter.engage_case(
        case_id=w.case_id, actor=_ACTOR, to=[_PEER], at=authored_at()
    ),
    "defer_case": lambda w: w.adapter.defer_case(
        case_id=w.case_id, actor=_ACTOR, to=[_PEER], at=authored_at()
    ),
    "close_case": lambda w: w.adapter.close_case(
        case_id=w.case_id, actor=_ACTOR, to=[_PEER], at=authored_at()
    ),
    "reject_close_case": lambda w: w.adapter.reject_close_case(
        case_id=w.case_id, actor=_ACTOR, close_sender=_PEER, at=authored_at()
    ),
    # The genesis entry is the creation's own Create, read back (ADR-0157).
    "record_case_created": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_case_created(
        create_activity_id=w.adapter_as(_CASE_ACTOR).create_case(
            case_id=w.case_id, actor=_CASE_ACTOR, to=[_PEER], at=authored_at()
        )[0]
    ),
    "record_report_added_to_case": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_report_added_to_case(
        report_id=str(w.report.id_),
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        offer_id=w.offer_id(holder=_CASE_ACTOR),
        offer_actor_id=_PEER,
        at=authored_at(),
    ),
    "record_participant_status_added": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_participant_status_added(
        status=w.status,
        participant=w.participant,
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        at=authored_at(),
    ),
    "record_case_status_added": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_case_status_added(
        status=w.case.current_status,
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        at=authored_at(),
    ),
    "record_case_participant_created": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_case_participant_created(
        participant=w.participant,
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        at=authored_at(),
    ),
    "record_case_participant_updated": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_case_participant_updated(
        participant=w.participant,
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        cause_id=_CAUSE_ID,
        at=authored_at(),
    ),
    "record_embargo_event_created": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_embargo_event_created(
        embargo=w.embargo,
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        at=authored_at(),
    ),
    "record_embargo_consent_created": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_embargo_consent_created(
        row=w.consent_row(EmbargoConsentState.UNINVITED),
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        at=authored_at(),
    ),
    "record_embargo_consent_updated": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_embargo_consent_updated(
        row=w.consent_row(EmbargoConsentState.AGREED),
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        cause_id=_CAUSE_ID,
        at=authored_at(),
    ),
    "record_vulnerability_item_added": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_vulnerability_item_added(
        item=make(VulnerabilityItem, cve="CVE-2026-0001"),
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        at=authored_at(),
    ),
    "record_case_reference_added": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_case_reference_added(
        reference=make(CaseReference, url={"href": "https://example.org/a"}),
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        at=authored_at(),
    ),
    "record_case_owner_updated": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_case_owner_updated(
        case=w.case, actor=_CASE_ACTOR, cause_id=_CAUSE_ID, at=authored_at()
    ),
    "record_case_announced": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).record_case_announced(
        case_id=w.case_id,
        actor=_CASE_ACTOR,
        object_id=w.case_id,
        at=authored_at(),
    ),
    "add_object_to_case": lambda w: w.adapter.add_object_to_case(
        actor=_ACTOR,
        object_id=w.note_id,
        case_id=w.case_id,
        to=[_PEER],
        at=authored_at(),
    ),
    "announce_vulnerability_case": lambda w: (
        w.adapter.announce_vulnerability_case(
            case_id=w.case_id,
            actor=_ACTOR,
            context_id=w.case_id,
            to=[_PEER],
            at=authored_at(),
        )
    ),
    "create_case_proposal": lambda w: w.adapter_as(_PEER).create_case_proposal(
        actor=_PEER,
        report_id=str(w.report.id_),
        case_actor_id=_CASE_ACTOR,
        to=[_CASE_ACTOR],
        at=authored_at(),
    ),
    "reject_case_proposal": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).reject_case_proposal(
        actor=_CASE_ACTOR,
        proposal=w.case_proposal(),
        to=[_PEER],
        at=authored_at(),
    ),
    "accept_case_proposal": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).accept_case_proposal(
        actor=_CASE_ACTOR,
        proposal=w.case_proposal(),
        to=[_PEER],
        result=w.case_id,
        at=authored_at(),
    ),
    "emit_prepared_create_case": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).emit_prepared_create_case(w.prepared_create_case()),
    # embargo
    "propose_embargo": lambda w: w.adapter.propose_embargo(
        embargo_id=str(w.embargo.id_),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        at=authored_at(),
    ),
    "accept_embargo": lambda w: w.adapter_as(_PEER).accept_embargo(
        proposal_id=w.proposal_id(holder=_PEER),
        case_id=w.case_id,
        actor=_PEER,
        to=[_ACTOR],
        at=authored_at(),
    ),
    "reject_embargo": lambda w: w.adapter_as(_PEER).reject_embargo(
        proposal_id=w.proposal_id(holder=_PEER),
        case_id=w.case_id,
        actor=_PEER,
        to=[_ACTOR],
        at=authored_at(),
    ),
    "undo_embargo_invite": lambda w: w.adapter.undo_embargo_invite(
        invite_id=w.proposal_id(),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        at=authored_at(),
    ),
    "activate_embargo": lambda w: w.adapter.activate_embargo(
        embargo_id=str(w.embargo.id_),
        proposal_id=w.proposal_id(),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        at=authored_at(),
    ),
    "reject_embargo_proposal": lambda w: w.adapter.reject_embargo_proposal(
        embargo_id=str(w.embargo.id_),
        proposal_id=w.proposal_id(),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        at=authored_at(),
    ),
    "announce_embargo": lambda w: w.adapter.announce_embargo(
        embargo_id=str(w.embargo.id_),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        at=authored_at(),
    ),
    "terminate_embargo": lambda w: w.adapter.terminate_embargo(
        embargo_id=str(w.embargo.id_),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        reason=TerminationReason.EARLY,
        at=authored_at(),
    ),
    "withdraw_from_embargo": lambda w: w.adapter.withdraw_from_embargo(
        embargo_id=str(w.embargo.id_),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        at=authored_at(),
    ),
    # actors
    "invite_actor_to_case": lambda w: w.adapter.invite_actor_to_case(
        invitee_id=_PEER,
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        roles=["vendor"],
        at=authored_at(),
    ),
    "accept_case_invite": lambda w: w.adapter_as(_PEER).accept_case_invite(
        invite_id=w.invite_id(), actor=_PEER, at=authored_at()
    ),
    "reject_case_invite": lambda w: w.adapter_as(_PEER).reject_case_invite(
        invite_id=w.invite_id(), actor=_PEER, at=authored_at()
    ),
    "invite_actor_to_full_case": lambda w: w.adapter.invite_actor_to_full_case(
        invitee_id=_PEER,
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        ledger_log_index=3,
        ledger_entry_hash="ab" * 32,
        at=authored_at(),
    ),
    "accept_full_case_invite": lambda w: w.adapter_as(
        _PEER
    ).accept_full_case_invite(
        invite_id=w.full_case_invite_id(),
        actor=_PEER,
        ledger_log_index=3,
        ledger_entry_hash="ab" * 32,
        at=authored_at(),
    ),
    "tentative_reject_full_case_invite": lambda w: w.adapter_as(
        _PEER
    ).tentative_reject_full_case_invite(
        invite_id=w.full_case_invite_id(),
        actor=_PEER,
        ledger_log_index=3,
        ledger_entry_hash="ab" * 32,
        at=authored_at(),
    ),
    "reject_full_case_invite": lambda w: w.adapter_as(
        _PEER
    ).reject_full_case_invite(
        invite_id=w.full_case_invite_id(),
        actor=_PEER,
        ledger_log_index=3,
        ledger_entry_hash="ab" * 32,
        at=authored_at(),
    ),
    "suggest_actor_to_case": lambda w: w.adapter_as(
        _PEER
    ).suggest_actor_to_case(
        recommended_id=_PEER,
        case_id=w.case_id,
        actor=_PEER,
        to=[_ACTOR],
        at=authored_at(),
    ),
    "offer_actor_to_case": lambda w: w.adapter.offer_actor_to_case(
        recommender_id=_PEER,
        recommended_id=_PEER,
        case_id=w.case_id,
        actor=_ACTOR,
        origin=w.recommendation_id(),
        to=[_ACTOR],
        at=authored_at(),
    ),
    "accept_case_participant_offer": lambda w: (
        w.adapter.accept_case_participant_offer(
            cp_offer_id=w.cp_offer_id(),
            actor=_ACTOR,
            to=[_CASE_ACTOR],
            at=authored_at(),
        )
    ),
    "reject_case_participant_offer": lambda w: (
        w.adapter.reject_case_participant_offer(
            cp_offer_id=w.cp_offer_id(),
            actor=_ACTOR,
            to=[_CASE_ACTOR],
            at=authored_at(),
        )
    ),
    "emit_accept_actor_recommendation": lambda w: (
        w.adapter.emit_accept_actor_recommendation(
            recommender_id=_PEER,
            recommendation_id=w.recommendation_id(),
            recommended_id=_PEER,
            case_id=w.case_id,
            actor=_ACTOR,
            to=[_PEER],
            at=authored_at(),
        )
    ),
    "emit_reject_actor_recommendation": lambda w: (
        w.adapter.emit_reject_actor_recommendation(
            recommender_id=_PEER,
            recommendation_id=w.recommendation_id(),
            recommended_id=_PEER,
            case_id=w.case_id,
            actor=_ACTOR,
            to=[_PEER],
            at=authored_at(),
        )
    ),
    "add_participant_to_case": lambda w: w.adapter.add_participant_to_case(
        participant_id=str(w.participant.id_),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        at=authored_at(),
    ),
    "remove_participant_from_case": lambda w: (
        w.adapter.remove_participant_from_case(
            participant_id=str(w.participant.id_),
            case_id=w.case_id,
            actor=_ACTOR,
            attributed_to=_PEER,
            to=[_PEER],
            at=authored_at(),
        )
    ),
    "add_participant_status_to_participant": lambda w: w.adapter_as(
        _PEER
    ).add_participant_status_to_participant(
        status_id=str(w.status.id_),
        participant_id=str(w.participant.id_),
        actor=_PEER,
        to=[_ACTOR],
        at=authored_at(),
    ),
    "offer_case_participant_role": lambda w: (
        w.adapter.offer_case_participant_role(
            case_id=w.case_id,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=_CASE_ACTOR,
            actor=_ACTOR,
            to=[_CASE_ACTOR],
            at=authored_at(),
        )
    ),
    "accept_case_participant_role": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).accept_case_participant_role(
        offer_id="https://example.org/offers/role-1",
        case_id=w.case_id,
        role=CVDRole.CASE_MANAGER,
        target_actor_id=_CASE_ACTOR,
        vendor_id=_ACTOR,
        actor=_CASE_ACTOR,
        to=[_ACTOR],
        at=authored_at(),
    ),
    "reject_case_participant_role": lambda w: w.adapter_as(
        _CASE_ACTOR
    ).reject_case_participant_role(
        offer_id="https://example.org/offers/role-2",
        case_id=w.case_id,
        role=CVDRole.CASE_MANAGER,
        target_actor_id=_CASE_ACTOR,
        vendor_id=_ACTOR,
        actor=_CASE_ACTOR,
        to=[_ACTOR],
        at=authored_at(),
    ),
    "propose_case_ownership_transfer": lambda w: (
        w.adapter.propose_case_ownership_transfer(
            case_id=w.case_id,
            transferee_id=_PEER,
            actor=_ACTOR,
            to=[_CASE_ACTOR],
            at=authored_at(),
        )
    ),
    "offer_case_ownership_transfer": lambda w: (
        w.adapter.offer_case_ownership_transfer(
            case_id=w.case_id,
            transferee_id=_PEER,
            actor=_ACTOR,
            to=[_PEER],
            at=authored_at(),
        )
    ),
    "accept_case_ownership_transfer": lambda w: w.adapter_as(
        _PEER
    ).accept_case_ownership_transfer(
        offer_id=w.ownership_offer_id(),
        actor=_PEER,
        to=[_ACTOR],
        at=authored_at(),
    ),
    "reject_case_ownership_transfer": lambda w: w.adapter_as(
        _PEER
    ).reject_case_ownership_transfer(
        offer_id=w.ownership_offer_id(),
        actor=_PEER,
        to=[_ACTOR],
        at=authored_at(),
    ),
    "withdraw_case_ownership_transfer": lambda w: (
        w.adapter.withdraw_case_ownership_transfer(
            offer_id=w.ownership_proposal_id(),
            actor=_ACTOR,
            to=[_CASE_ACTOR],
            at=authored_at(),
        )
    ),
    # faults
    "emit_processing_fault": lambda w: w.adapter.emit_processing_fault(
        actor=_ACTOR,
        failed_activity_id="https://example.org/activities/failed-1",
        failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
        to=[_PEER],
        at=authored_at(),
    ),
    "refusal_notice": lambda w: w.adapter.refusal_notice(
        case_id="https://example.org/cases/refused-1",
        actor=_ACTOR,
        refused_activity=json.loads(
            dump_outbound_body(add_fix_readiness_to_participant())
        ),
        asserter=_PEER,
        reason="a precondition did not hold",
        at=authored_at(),
    ),
}


def _port_methods() -> set[str]:
    return {
        name
        for name, _ in inspect.getmembers(
            TriggerActivityPort, inspect.isfunction
        )
        if not name.startswith("_")
    }


@pytest.fixture
def world():
    world = _World()
    yield world
    world.close()


def test_every_port_activity_method_has_a_recipe():
    """Ratchet: a new outbound activity must be audited here."""
    assert set(RECIPES) == _port_methods() - _NOT_AN_ACTIVITY


@pytest.mark.spec("VM-08-003")
@pytest.mark.spec("AKM-03-001")
@pytest.mark.spec("AKM-02-003")
@pytest.mark.spec("AKM-02-008")
@pytest.mark.parametrize("method", sorted(RECIPES))
def test_the_activity_is_sealed_complete(world, method):
    result = RECIPES[method](world)
    if isinstance(result, tuple):
        activity_id, blob = result
    else:
        activity_id, blob = result, None

    _store, sealed = world.sealed_by(activity_id)
    if blob is not None:
        assert sealed.body == blob, f"{method} returned a blob it did not seal"

    body = json.loads(sealed.body)
    assert body["id"] == activity_id
    if (
        "to"
        in inspect.signature(getattr(TriggerActivityPort, method)).parameters
    ):
        assert body.get("to"), (
            f"{method} sealed an activity with no recipients"
        )
    if body["type"] in _INLINE_OBJECT_ACTIVITY_TYPES:
        obj = body.get("object")
        assert isinstance(obj, dict) and obj.get("type"), (
            f"{method} emitted {body['type']} with a non-inline object"
            f" {obj!r} (AKM-03-003)"
        )
    # MV-10-001 now lives in the factory: nothing downstream collapses a case
    # in ``target`` or ``context`` any more, so a case there is either its
    # URI or the selective-disclosure stub — never the full object.  Checked
    # at every depth: an Accept embeds the Offer or Invite it answers, and a
    # read-back-rehydrated embedded activity is where a full case leaked.
    # A case carried as the ``object`` carries its participants (CBT-01-007)
    # and, as this prototype's choice, the reports its sender holds
    # (AKM-02-004) as objects — the recipient seeds its replica from them, and
    # the outbox no longer expands ids at delivery time.  The world holds its
    # report, so a bare report id here is a regression too.
    obj = body.get("object")
    if (
        isinstance(obj, dict)
        and obj.get("type") == "VulnerabilityCase"
        and method not in _CASE_AS_STORED
    ):
        for field in ("caseParticipants", "vulnerabilityReports"):
            bare = [x for x in obj.get(field, []) if not isinstance(x, dict)]
            assert not bare, (
                f"{method} put a VulnerabilityCase in object whose {field}"
                f" holds bare ids {bare} (CBT-01-007 for participants,"
                " AKM-02-004 for reports)"
            )
    leaks = _full_case_paths(body)
    assert not leaks, (
        f"{method} put a full VulnerabilityCase in a reference slot:"
        f" {leaks}; address the case by URI or send the stub"
        " (MV-10-001, AKM-02-008)"
    )
    copies = _carried_case_copies(body)
    assert not copies, (
        f"{method} carried a copy of the case where an act names it:"
        f" {copies}; send its typed reference (AKM-03-004, ADR-0165)"
    )


def _carried_case_copies(value: Any, path: str = "body") -> list[str]:
    """Paths of every case an act that names its case carries in full.

    A ``Join``, ``Ignore``, ``Leave`` or ``Offer`` whose ``object`` is a
    case carries only its ``id`` and ``type`` (AKM-03-004); checked at every
    depth, since an ``Accept`` or ``Reject`` embeds the act it answers.
    """
    found: list[str] = []
    if isinstance(value, dict):
        obj = value.get("object")
        if (
            value.get("type") in CASE_NAMING_ACTIVITY_TYPES
            and isinstance(obj, dict)
            and obj.get("type") == "VulnerabilityCase"
            and not is_case_reference_shape(obj)
        ):
            found.append(f"{path}.object")
        for key, child in value.items():
            found.extend(_carried_case_copies(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_carried_case_copies(item, f"{path}[{index}]"))
    return found


def _full_case_paths(value: Any, path: str = "body") -> list[str]:
    """Paths of every case dict in a ``target``/``context`` slot, any depth.

    A stub names itself ``VulnerabilityCaseStub`` (CM-11-013), so any inline
    ``VulnerabilityCase`` in a reference slot is the case itself.
    """
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if (
                key in ("target", "context")
                and isinstance(child, dict)
                and child.get("type") == "VulnerabilityCase"
            ):
                found.append(child_path)
            found.extend(_full_case_paths(child, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_full_case_paths(item, f"{path}[{index}]"))
    return found


@pytest.mark.spec("CM-17-003")
def test_invite_roles_survive_into_the_sealed_body(world):
    """The roles the Invite carries reach the wire (regression: a role dropped
    on the old re-read path blocked the invitee's CSB-15-002 admission)."""
    _, blob = RECIPES["invite_actor_to_case"](world)
    assert json.loads(blob)["roles"] == ["vendor"]


@pytest.mark.spec("CM-16-003")
def test_suggested_roles_survive_into_the_sealed_body(world):
    _, blob = world.adapter_as(_PEER).suggest_actor_to_case(
        recommended_id=_PEER,
        case_id=world.case_id,
        actor=_PEER,
        to=[_ACTOR],
        roles=["deployer"],
        at=authored_at(),
    )
    assert json.loads(blob)["suggestedRoles"] == ["deployer"]


#: Where each role-delegation recipe carries the delegate actor in its sealed
#: body: the Offer's ``target``, or the ``target`` of the Offer an answer
#: embeds.
_ROLE_DELEGATE_PATHS: dict[str, tuple[str, ...]] = {
    "offer_case_participant_role": ("target",),
    "accept_case_participant_role": ("object", "target"),
    "reject_case_participant_role": ("object", "target"),
}


@pytest.mark.spec("AKM-02-006")
@pytest.mark.parametrize("method", sorted(_ROLE_DELEGATE_PATHS))
def test_a_role_delegate_given_by_uri_carries_no_invented_field(world, method):
    _, blob = RECIPES[method](world)
    delegate: Any = json.loads(blob)
    for key in _ROLE_DELEGATE_PATHS[method]:
        delegate = delegate[key]
    assert isinstance(delegate, dict)
    invented = ("published", "updated", "inbox", "outbox")
    assert [key for key in invented if key in delegate] == []


#: Methods that name the held peer ``_PEER``, with the path to the actor in
#: the sealed body.
_HELD_ACTOR_PATHS: dict[str, tuple[str, ...]] = {
    "invite_actor_to_case": ("object",),
    "invite_actor_to_full_case": ("object",),
    "suggest_actor_to_case": ("object",),
    "offer_case_ownership_transfer": ("target",),
    "propose_case_ownership_transfer": ("object", "target"),
}


def _carried(blob: str, path: tuple[str, ...]) -> dict[str, Any]:
    actor: Any = json.loads(blob)
    for key in path:
        actor = actor[key]
    assert isinstance(actor, dict)
    return actor


@pytest.mark.spec("AKM-05-005")
@pytest.mark.parametrize("method", sorted(_HELD_ACTOR_PATHS))
def test_an_actor_the_sender_holds_travels_as_held(world, method):
    """The adapter reads its held record of the named actor (ADR-0159)."""
    _, blob = RECIPES[method](world)
    actor = _carried(blob, _HELD_ACTOR_PATHS[method])
    assert actor["id"] == _PEER
    assert actor["type"] == "Service"
    assert actor["name"] == "Vendor"
    # Its own ``published``, not this build's clock; and no endpoint the
    # record does not state (AKM-02-006).
    assert (
        actor["published"]
        == world.vendor.model_dump(mode="json", by_alias=True)["published"]
    )
    assert "inbox" not in actor
    assert "outbox" not in actor


@pytest.mark.spec("AKM-05-017")
@pytest.mark.parametrize("method", sorted(_ROLE_DELEGATE_PATHS))
def test_an_actor_the_sender_does_not_hold_travels_as_a_reference(
    world, method
):
    """Only a URI is held for the delegate, so it travels as id and type."""
    # Neither sender holds the delegate's record.
    assert world.store(_ACTOR).read(_CASE_ACTOR) is None
    assert world.store(_CASE_ACTOR).read(_CASE_ACTOR) is None
    _, blob = RECIPES[method](world)
    actor = _carried(blob, _ROLE_DELEGATE_PATHS[method])
    actor.pop("@context", None)
    assert actor == {"id": _CASE_ACTOR, "type": "Actor"}


@pytest.mark.spec("AKM-05-017")
def test_a_uri_only_peer_record_travels_as_a_reference(world):
    """The minimal peer of ``_record_named_peer`` holds only the URI."""
    from vultron.core.models.actor import CoreActor

    world.dl.create(
        make(CoreActor, id_=_CASE_ACTOR, published=None, updated=None)
    )
    _, blob = RECIPES["offer_case_participant_role"](world)
    actor = _carried(blob, ("target",))
    actor.pop("@context", None)
    assert actor == {"id": _CASE_ACTOR, "type": "Actor"}


@pytest.mark.spec("AKM-02-006")
@pytest.mark.spec("OX-06-002")
@pytest.mark.parametrize(
    "method",
    ["emit_accept_actor_recommendation", "emit_reject_actor_recommendation"],
)
def test_a_rebuilt_recommendation_is_the_same_on_every_build(
    world, method, monkeypatch
):
    """The CASE_MANAGER's rebuild of the recommendation reads no clock.

    Two builds from one store, an hour apart, embed the same recommendation:
    nothing in it is minted from this actor's clock (AKM-02-006), so every
    rebuild under the recommendation's id carries the same body (OX-06-002).
    """
    from datetime import timedelta

    from vultron.core.models._helpers import clock as helpers_clock, now_utc
    from vultron.demo.determinism import SteppingClock

    emit = getattr(world.adapter, method)

    def embedded() -> dict[str, Any]:
        _, blob = emit(
            recommender_id=_PEER,
            recommendation_id="https://example.org/activities/recommendation",
            recommended_id=_PEER,
            case_id=world.case_id,
            actor=_ACTOR,
            to=[_PEER],
            at=authored_at(),
        )
        recommendation: dict[str, Any] = json.loads(blob)["object"]
        return recommendation

    first = embedded()
    monkeypatch.setattr(
        helpers_clock,
        "datetime",
        SteppingClock(now_utc() + timedelta(hours=1), step=timedelta(0)),
    )
    second = embedded()

    assert "published" not in first
    assert "updated" not in first
    assert first == second


@pytest.mark.spec("AKM-02-006")
def test_a_rebuilt_close_leave_carries_no_time(world):
    """The rejecter's rebuild of the owner's close ``Leave`` carries no time.

    The owner stated the Leave's ``published``, which this actor does not
    hold (AKM-02-006), so the Reject's own instant is not stamped on the
    embedded Leave.
    """
    at = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    _, blob = world.adapter.reject_close_case(
        case_id=world.case_id, actor=_ACTOR, close_sender=_PEER, at=at
    )
    body = json.loads(blob)
    leave = body["object"]

    assert datetime.fromisoformat(body["published"]) == at
    assert "published" not in leave
    assert "updated" not in leave
