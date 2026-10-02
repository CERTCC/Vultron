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
- put a fully inline ``object`` on every initiating activity (AKM-03-001) —
  the outbox no longer expands a bare reference at delivery time, so a factory
  that emitted one would now be refused rather than repaired;
- address the recipients it was given;
- carry a case in ``target`` only as its URI or the selective-disclosure stub
  (MV-10-001), since nothing downstream collapses it any more.

The recipe table is a ratchet: a port method with no recipe fails the test, so
a new outbound activity cannot be added without being audited here.
"""

import inspect
import json
from collections.abc import Callable
from typing import Any

import pytest

from test.support.received import archive_received
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.driving.fastapi.outbox_delivery import (
    _INLINE_OBJECT_ACTIVITY_TYPES,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronCreateCaseActivity
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_ACTOR = "https://example.org/actors/coordinator"
_PEER = "https://example.org/actors/vendor"
_CASE_ACTOR = "https://example.org/actors/case-actor"

#: Port methods that build a domain *object*, not an outbound activity.
_NOT_AN_ACTIVITY = frozenset({"create_note"})


class _World:
    """A seeded store and the ids the recipes need."""

    def __init__(self, dl: SqliteDataLayer) -> None:
        self.dl = dl
        self.adapter = TriggerActivityAdapter(dl)
        self.case_id: str = "https://example.org/cases/audit-case"
        self.vendor = as_Service(id_=_PEER, name="Vendor")
        dl.create(self.vendor)
        self.report = as_VulnerabilityReport(name="CVE-2026-1", content="PoC")
        dl.create(self.report)
        self.participant = as_CaseParticipant(
            context=self.case_id, attributed_to=_PEER
        )
        dl.create(self.participant)
        # The case names its participant and report by id, as a stored case
        # does; a case put on the wire must carry them inline (CBT-01-007).
        self.case = as_VulnerabilityCase(
            id_=self.case_id,
            name="CVE-2026-1",
            attributed_to=_ACTOR,
            case_participants=[str(self.participant.id_)],
            vulnerability_reports=[str(self.report.id_)],
        )
        dl.create(self.case)
        self.status = ParticipantStatus(context=self.case_id)
        dl.create(self.status)
        self.embargo = as_EmbargoEvent(
            context=self.case_id, end_time=days_from_now_utc(45)
        )
        dl.create(self.embargo)
        note_id, _ = self.adapter.create_note(
            name="n",
            content="c",
            context_id=self.case_id,
            attributed_to=_ACTOR,
        )
        self.note_id = note_id

    # -- prerequisites other recipes build on ----------------------------------

    def offer_id(self) -> str:
        offer_id, _ = self.adapter.submit_report(
            report_id=str(self.report.id_),
            actor=_PEER,
            to=_ACTOR,
            target=_ACTOR,
        )
        return offer_id

    def invite_id(self) -> str:
        """An Invite as the invitee holds it: archived by intake (CLP-10-017)."""
        invite_id, _ = self.adapter.invite_actor_to_case(
            invitee_id=_PEER, case_id=self.case_id, actor=_ACTOR, to=[_PEER]
        )
        archive_received(self.dl, self.dl.read(invite_id))
        return invite_id

    def recommendation_id(self) -> str:
        rec_id, _ = self.adapter.suggest_actor_to_case(
            recommended_id=_PEER,
            case_id=self.case_id,
            actor=_PEER,
            to=[_ACTOR],
        )
        return rec_id

    def cp_offer_id(self) -> str:
        cp_id, _ = self.adapter.offer_actor_to_case(
            recommender_id=_PEER,
            recommended_id=_PEER,
            case_id=self.case_id,
            actor=_ACTOR,
            origin=self.recommendation_id(),
            to=[_ACTOR],
        )
        return cp_id

    def proposal_id(self) -> str:
        proposal_id, _ = self.adapter.propose_embargo(
            embargo_id=str(self.embargo.id_),
            case_id=self.case_id,
            actor=_ACTOR,
            to=[_PEER],
        )
        return proposal_id

    def case_proposal(self) -> dict[str, Any]:
        _, blob = self.adapter.create_case_proposal(
            actor=_PEER,
            report_id=str(self.report.id_),
            case_actor_id=_CASE_ACTOR,
            to=[_CASE_ACTOR],
        )
        proposal = json.loads(blob)["object"]
        assert isinstance(proposal, dict)
        return proposal

    def ownership_offer_id(self) -> str:
        offer_id, _ = self.adapter.offer_case_ownership_transfer(
            case_id=self.case_id, transferee_id=_PEER, actor=_ACTOR, to=[_PEER]
        )
        return offer_id

    def prepared_create_case(self) -> dict[str, Any]:
        # Mirrors ``WriteCreateCaseMarkerNode._build_case_object``: the
        # marker's payload carries the participants and reports as objects
        # (ADR-0041 AC-5, CBT-01-007); the adapter re-sends it unchanged
        # (CP-05-005), so the audit hands it the shape production does.
        stored = self.dl.read(self.case_id, raise_on_missing=True)
        assert stored is not None
        case_dict = As2WireRenderAdapter().render(
            stored.model_copy(
                update={
                    "case_participants": [self.participant],
                    "vulnerability_reports": [self.report],
                }
            )
        )
        return VultronCreateCaseActivity(
            actor=_CASE_ACTOR,
            object_=case_dict,
            context=self.case_id,
            to=[_PEER],
        ).model_dump(by_alias=True)


Recipe = Callable[[_World], Any]

RECIPES: dict[str, Recipe] = {
    # notes
    "create_note_activity": lambda w: w.adapter.create_note_activity(
        actor=_ACTOR, note_id=w.note_id, to=[_PEER]
    ),
    "add_note_to_case": lambda w: w.adapter.add_note_to_case(
        note_id=w.note_id, case_id=w.case_id, actor=_ACTOR, to=[_PEER]
    ),
    # reports
    "submit_report": lambda w: w.adapter.submit_report(
        report_id=str(w.report.id_), actor=_PEER, to=_ACTOR, target=_ACTOR
    ),
    "validate_report": lambda w: w.adapter.validate_report(
        offer_id=w.offer_id(),
        report_id=str(w.report.id_),
        actor=_ACTOR,
        to=[_PEER],
    ),
    "close_report": lambda w: w.adapter.close_report(
        offer_id=w.offer_id(),
        report_id=str(w.report.id_),
        actor=_ACTOR,
        to=[_PEER],
    ),
    "invalidate_report": lambda w: w.adapter.invalidate_report(
        offer_id=w.offer_id(), actor=_ACTOR, to=[_PEER]
    ),
    "ack_report": lambda w: w.adapter.ack_report(
        offer_id=w.offer_id(), actor=_ACTOR, to=[_PEER]
    ),
    # cases
    "create_case": lambda w: w.adapter.create_case(
        case_id=w.case_id, actor=_ACTOR, to=[_PEER]
    ),
    "engage_case": lambda w: w.adapter.engage_case(
        case_id=w.case_id, actor=_ACTOR, to=[_PEER]
    ),
    "defer_case": lambda w: w.adapter.defer_case(
        case_id=w.case_id, actor=_ACTOR, to=[_PEER]
    ),
    "close_case": lambda w: w.adapter.close_case(
        case_id=w.case_id, actor=_ACTOR, to=[_PEER]
    ),
    "reject_close_case": lambda w: w.adapter.reject_close_case(
        case_id=w.case_id, actor=_ACTOR, close_sender=_PEER
    ),
    "add_object_to_case": lambda w: w.adapter.add_object_to_case(
        actor=_ACTOR, object_id=w.note_id, case_id=w.case_id
    ),
    "announce_vulnerability_case": lambda w: (
        w.adapter.announce_vulnerability_case(
            case_id=w.case_id, actor=_ACTOR, context_id=w.case_id, to=[_PEER]
        )
    ),
    "create_case_proposal": lambda w: w.adapter.create_case_proposal(
        actor=_PEER,
        report_id=str(w.report.id_),
        case_actor_id=_CASE_ACTOR,
        to=[_CASE_ACTOR],
    ),
    "reject_case_proposal": lambda w: w.adapter.reject_case_proposal(
        actor=_CASE_ACTOR, proposal=w.case_proposal(), to=[_PEER]
    ),
    "accept_case_proposal": lambda w: w.adapter.accept_case_proposal(
        actor=_CASE_ACTOR,
        proposal=w.case_proposal(),
        to=[_PEER],
        result=w.case_id,
    ),
    "emit_prepared_create_case": lambda w: w.adapter.emit_prepared_create_case(
        w.prepared_create_case()
    ),
    # embargo
    "propose_embargo": lambda w: w.adapter.propose_embargo(
        embargo_id=str(w.embargo.id_),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
    ),
    "accept_embargo": lambda w: w.adapter.accept_embargo(
        proposal_id=w.proposal_id(),
        case_id=w.case_id,
        actor=_PEER,
        to=[_ACTOR],
    ),
    "reject_embargo": lambda w: w.adapter.reject_embargo(
        proposal_id=w.proposal_id(),
        case_id=w.case_id,
        actor=_PEER,
        to=[_ACTOR],
    ),
    "announce_embargo": lambda w: w.adapter.announce_embargo(
        embargo_id=str(w.embargo.id_),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
    ),
    "terminate_embargo": lambda w: w.adapter.terminate_embargo(
        embargo_id=str(w.embargo.id_),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
    ),
    # actors
    "invite_actor_to_case": lambda w: w.adapter.invite_actor_to_case(
        invitee_id=_PEER,
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
        roles=["vendor"],
    ),
    "accept_case_invite": lambda w: w.adapter.accept_case_invite(
        invite_id=w.invite_id(), actor=_PEER
    ),
    "reject_case_invite": lambda w: w.adapter.reject_case_invite(
        invite_id=w.invite_id(), actor=_PEER
    ),
    "suggest_actor_to_case": lambda w: w.adapter.suggest_actor_to_case(
        recommended_id=_PEER, case_id=w.case_id, actor=_PEER, to=[_ACTOR]
    ),
    "offer_actor_to_case": lambda w: w.adapter.offer_actor_to_case(
        recommender_id=_PEER,
        recommended_id=_PEER,
        case_id=w.case_id,
        actor=_ACTOR,
        origin=w.recommendation_id(),
        to=[_ACTOR],
    ),
    "accept_case_participant_offer": lambda w: (
        w.adapter.accept_case_participant_offer(
            cp_offer_id=w.cp_offer_id(), actor=_ACTOR, to=[_CASE_ACTOR]
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
        )
    ),
    "accept_actor_recommendation": lambda w: (
        w.adapter.accept_actor_recommendation(
            recommended_id=_PEER,
            recommender_id=_PEER,
            recommendation_id=w.recommendation_id(),
            case_id=w.case_id,
            actor=_ACTOR,
            to=[_PEER],
        )
    ),
    "add_participant_to_case": lambda w: w.adapter.add_participant_to_case(
        participant_id=str(w.participant.id_),
        case_id=w.case_id,
        actor=_ACTOR,
        to=[_PEER],
    ),
    "add_participant_status_to_participant": lambda w: (
        w.adapter.add_participant_status_to_participant(
            status_id=str(w.status.id_),
            participant_id=str(w.participant.id_),
            actor=_PEER,
            to=[_ACTOR],
        )
    ),
    "offer_case_participant_role": lambda w: (
        w.adapter.offer_case_participant_role(
            case_id=w.case_id,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=_CASE_ACTOR,
            actor=_ACTOR,
            to=[_CASE_ACTOR],
        )
    ),
    "accept_case_participant_role": lambda w: (
        w.adapter.accept_case_participant_role(
            offer_id="https://example.org/offers/role-1",
            case_id=w.case_id,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=_CASE_ACTOR,
            vendor_id=_ACTOR,
            actor=_CASE_ACTOR,
            to=[_ACTOR],
        )
    ),
    "reject_case_participant_role": lambda w: (
        w.adapter.reject_case_participant_role(
            offer_id="https://example.org/offers/role-2",
            case_id=w.case_id,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=_CASE_ACTOR,
            vendor_id=_ACTOR,
            actor=_CASE_ACTOR,
            to=[_ACTOR],
        )
    ),
    "offer_case_ownership_transfer": lambda w: (
        w.adapter.offer_case_ownership_transfer(
            case_id=w.case_id, transferee_id=_PEER, actor=_ACTOR, to=[_PEER]
        )
    ),
    "accept_case_ownership_transfer": lambda w: (
        w.adapter.accept_case_ownership_transfer(
            offer_id=w.ownership_offer_id(), actor=_PEER, to=[_ACTOR]
        )
    ),
    # faults
    "emit_processing_fault": lambda w: w.adapter.emit_processing_fault(
        actor=_ACTOR,
        failed_activity_id="https://example.org/activities/failed-1",
        failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED,
        to=[_PEER],
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
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    yield _World(dl)
    dl.clear_all()
    dl.close()


def test_every_port_activity_method_has_a_recipe():
    """Ratchet: a new outbound activity must be audited here."""
    assert set(RECIPES) == _port_methods() - _NOT_AN_ACTIVITY


@pytest.mark.spec("VM-08-003")
@pytest.mark.spec("AKM-03-001")
@pytest.mark.parametrize("method", sorted(RECIPES))
def test_the_activity_is_sealed_complete(world, method):
    result = RECIPES[method](world)
    if isinstance(result, tuple):
        activity_id, blob = result
    else:
        activity_id, blob = result, None

    sealed = read_sealed_body(world.dl, activity_id)
    assert sealed is not None, (
        f"{method} did not seal a body for {activity_id}"
    )
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
            f" {obj!r} (AKM-03-001)"
        )
    # MV-10-001 now lives in the factory: nothing downstream collapses a case
    # in ``target`` or ``context`` any more, so a case there is either its
    # URI or the selective-disclosure stub — never the full object.  Checked
    # at every depth: an Accept embeds the Offer or Invite it answers, and a
    # read-back-rehydrated embedded activity is where a full case leaked.
    # CBT-01-007: a case carried as the ``object`` carries its participants and
    # reports as objects — the recipient seeds its replica from them, and the
    # outbox no longer expands ids at delivery time.
    obj = body.get("object")
    if isinstance(obj, dict) and obj.get("type") == "VulnerabilityCase":
        for field in ("caseParticipants", "vulnerabilityReports"):
            bare = [x for x in obj.get(field, []) if not isinstance(x, dict)]
            assert not bare, (
                f"{method} put a VulnerabilityCase in object whose {field}"
                f" holds bare ids {bare} (CBT-01-007)"
            )
    leaks = _full_case_paths(body)
    assert not leaks, (
        f"{method} put a full VulnerabilityCase in a reference slot:"
        f" {leaks}; address the case by URI or send the stub"
        " (MV-10-001, AKM-02-003)"
    )


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
    _, blob = world.adapter.suggest_actor_to_case(
        recommended_id=_PEER,
        case_id=world.case_id,
        actor=_PEER,
        to=[_ACTOR],
        roles=["deployer"],
    )
    assert json.loads(blob)["suggestedRoles"] == ["deployer"]
