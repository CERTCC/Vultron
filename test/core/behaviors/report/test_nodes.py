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

"""
Tests for report validation behavior tree nodes.

Uses BTTestScenario (from ``test.core.behaviors.bt_harness``) as the single
execution path; no direct ``node.update()`` / ``node.blackboard.register_key()``
calls appear here.

Scope: RM-transition edge cases (same-state writes, illegal jumps,
re-validation) and the two addressee-resolution helpers. Per-node coverage lives
in ``test/core/behaviors/report/nodes/``, which mirrors
``vultron/core/behaviors/report/nodes/`` per CS-18-004 — this file must not
re-add a copy of a test that lives there (CONCERN-3048).

Per GitHub issue #401 and specs/behavior-tree-node-design.yaml.
"""

import pytest

from vultron.core.behaviors.report.nodes.case_creation import (
    _collect_create_case_addressees,
)
from vultron.core.behaviors.report.nodes.emit import _compute_report_addressees
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models._helpers import _report_phase_status_id
from vultron.core.models.vultron_types import (
    VultronOffer,
    VultronReport,
)
from vultron.core.behaviors.report.nodes import (
    TransitionRMtoClosed,
    TransitionRMtoInvalid,
    TransitionRMtoValid,
)
from vultron.core.models.dimensions import RmDimension
from vultron.core.states.rm import RM
from test.core.behaviors.bt_harness import BTTestScenario

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def actor(bt_scenario: BTTestScenario) -> VultronCaseActor:
    """Create a test actor and persist it in the scenario DataLayer.

    Its id *is* the scenario's actor: every node here executes as ``actor.id_``,
    and a BT's store follows its executing actor (ADR-0073), so a generated id
    would run each node against an empty store.
    """
    obj = VultronCaseActor(id_=bt_scenario.actor_id, name="Test Actor")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def report(bt_scenario: BTTestScenario) -> VultronReport:
    """Create a test report and persist it in the scenario DataLayer."""
    obj = VultronReport(
        name="TEST-001",
        content="Test vulnerability report",
    )
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def offer(
    bt_scenario: BTTestScenario, report: VultronReport, actor: VultronCaseActor
) -> VultronOffer:
    """Create a test offer and persist it in the scenario DataLayer."""
    obj = VultronOffer(actor=actor.id_, object_=report.id_)
    bt_scenario.dl.create(obj)
    offer_record = VultronOfferRecord(
        offer_id=obj.id_,
        report_id=report.id_,
        offer_actor_id=actor.id_,
        offer_to=[],
    )
    bt_scenario.dl.create(offer_record)
    return obj


# ============================================================================
# RM Transition Edge Cases
# ============================================================================


def test_transition_rm_to_valid_same_state(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case_with_participant: VulnerabilityCase,
) -> None:
    """TransitionRMtoValid succeeds on a same-state write (AC-3)."""
    valid_status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.VALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.VALID),
    )
    bt_scenario.seed(valid_status)

    result = bt_scenario.run(
        TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
        case_id=case_with_participant.id_,
    )
    bt_scenario.assert_success(result)


def test_transition_rm_to_valid_invalid_jump(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoValid returns FAILURE for an illegal RM jump (AC-2)."""
    closed_status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.CLOSED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.CLOSED),
    )
    bt_scenario.seed(closed_status)

    result = bt_scenario.run(
        TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_transition_rm_to_invalid_same_state(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoInvalid succeeds on a same-state write (AC-3)."""
    invalid_status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.INVALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.INVALID),
    )
    bt_scenario.seed(invalid_status)

    result = bt_scenario.run(
        TransitionRMtoInvalid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_transition_rm_to_invalid_invalid_jump(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoInvalid returns FAILURE for an illegal RM jump (AC-2)."""
    closed_status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.CLOSED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.CLOSED),
    )
    bt_scenario.seed(closed_status)

    result = bt_scenario.run(
        TransitionRMtoInvalid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


def test_transition_rm_to_valid_from_invalid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
    case_with_participant: VulnerabilityCase,
) -> None:
    """TransitionRMtoValid succeeds from RM.INVALID (re-validation path)."""
    invalid_status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.INVALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.INVALID),
    )
    bt_scenario.seed(invalid_status)

    result = bt_scenario.run(
        TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
        case_id=case_with_participant.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.VALID, actor_id=actor.id_)


def test_transition_rm_to_closed_valid_from_invalid(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoClosed succeeds from RM.INVALID (valid adjacent step)."""
    invalid_status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.INVALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.INVALID),
    )
    bt_scenario.seed(invalid_status)

    result = bt_scenario.run(
        TransitionRMtoClosed(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.CLOSED, actor_id=actor.id_)


def test_transition_rm_to_closed_same_state(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoClosed succeeds on a same-state write (AC-3)."""
    closed_status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.CLOSED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.CLOSED),
    )
    bt_scenario.seed(closed_status)

    result = bt_scenario.run(
        TransitionRMtoClosed(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)


def test_transition_rm_to_closed_valid_from_accepted(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoClosed succeeds from RM.ACCEPTED (valid adjacent step)."""
    accepted_status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.ACCEPTED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.ACCEPTED),
    )
    bt_scenario.seed(accepted_status)

    result = bt_scenario.run(
        TransitionRMtoClosed(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.CLOSED, actor_id=actor.id_)


def test_transition_rm_to_closed_valid_from_deferred(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoClosed succeeds from RM.DEFERRED (valid adjacent step)."""
    deferred_status = ParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.DEFERRED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm=RmDimension(state=RM.DEFERRED),
    )
    bt_scenario.seed(deferred_status)

    result = bt_scenario.run(
        TransitionRMtoClosed(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_success(result)
    bt_scenario.assert_rm_state(report.id_, RM.CLOSED, actor_id=actor.id_)


def test_transition_rm_to_closed_invalid_jump_from_received(
    bt_scenario: BTTestScenario,
    actor: VultronCaseActor,
    report: VultronReport,
    offer: VultronOffer,
) -> None:
    """TransitionRMtoClosed returns FAILURE for RECEIVED→CLOSED (AC-2)."""
    result = bt_scenario.run(
        TransitionRMtoClosed(report_id=report.id_, offer_id=offer.id_),
        actor_id=actor.id_,
    )
    bt_scenario.assert_failure(result)


# ============================================================================
# AC-4: Domain facts read from VultronOfferRecord, not wire Offer
# ============================================================================


class TestComputeReportAddresseesFallback:
    """_compute_report_addressees reads from VultronOfferRecord, not wire Offer.

    Per ADR-0035 DL-06-001: when no case is found for a report, the fallback
    addressee is the offer submitter's actor ID, which must come from the core
    VultronOfferRecord — not from getattr(offer, "actor", None).
    """

    def test_returns_offer_actor_when_no_case(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Fallback path returns offer_actor_id from VultronOfferRecord."""
        from typing import cast
        from vultron.core.ports.case_persistence import CaseOutboxPersistence

        actor_id = "urn:test:actor:1"
        submitter_id = "urn:test:submitter:1"
        offer_record = VultronOfferRecord(
            offer_id="urn:test:offer:1",
            report_id="urn:test:report:1",
            offer_actor_id=submitter_id,
            offer_to=[],
        )
        result = _compute_report_addressees(
            report_id="urn:test:report:no-case",
            actor_id=actor_id,
            offer_record=offer_record,
            dl=cast(CaseOutboxPersistence, bt_scenario.dl),
        )
        assert result == [submitter_id]

    def test_returns_none_when_no_offer_record(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Fallback path returns None when offer_record is None."""
        from typing import cast
        from vultron.core.ports.case_persistence import CaseOutboxPersistence

        result = _compute_report_addressees(
            report_id="urn:test:report:no-case",
            actor_id="urn:test:actor:1",
            offer_record=None,
            dl=cast(CaseOutboxPersistence, bt_scenario.dl),
        )
        assert result is None

    def test_excludes_self_from_addressees(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Fallback path excludes actor_id (self) from addressees."""
        from typing import cast
        from vultron.core.ports.case_persistence import CaseOutboxPersistence

        actor_id = "urn:test:actor:self"
        offer_record = VultronOfferRecord(
            offer_id="urn:test:offer:2",
            report_id="urn:test:report:2",
            offer_actor_id=actor_id,
            offer_to=[],
        )
        result = _compute_report_addressees(
            report_id="urn:test:report:no-case",
            actor_id=actor_id,
            offer_record=offer_record,
            dl=cast(CaseOutboxPersistence, bt_scenario.dl),
        )
        assert result is None


class TestCollectCreateCaseAddresseesFromRecord:
    """_collect_create_case_addressees reads offer_to/offer_actor_id from VultronOfferRecord.

    Per ADR-0035 DL-06-001: addressees are computed from the core
    VultronOfferRecord, not from getattr(offer, "to"/"actor", None).
    """

    def test_includes_offer_to_recipients(self) -> None:
        """offer_to list from VultronOfferRecord is included in addressees."""
        actor_id = "urn:test:actor:creator"
        recipient_id = "urn:test:recipient:1"
        offer_record = VultronOfferRecord(
            offer_id="urn:test:offer:3",
            report_id="urn:test:report:3",
            offer_actor_id="urn:test:submitter:3",
            offer_to=[recipient_id],
        )
        result = _collect_create_case_addressees(
            actor=actor_id,
            report=None,
            offer_record=offer_record,
            actor_id=actor_id,
        )
        assert recipient_id in result

    def test_includes_offer_actor_id(self) -> None:
        """offer_actor_id from VultronOfferRecord is included in addressees."""
        actor_id = "urn:test:actor:creator"
        submitter_id = "urn:test:submitter:4"
        offer_record = VultronOfferRecord(
            offer_id="urn:test:offer:4",
            report_id="urn:test:report:4",
            offer_actor_id=submitter_id,
            offer_to=[],
        )
        result = _collect_create_case_addressees(
            actor=actor_id,
            report=None,
            offer_record=offer_record,
            actor_id=actor_id,
        )
        assert submitter_id in result

    def test_excludes_actor_id_from_addressees(self) -> None:
        """actor_id (creator) is excluded from the addressee list."""
        actor_id = "urn:test:actor:creator"
        offer_record = VultronOfferRecord(
            offer_id="urn:test:offer:5",
            report_id="urn:test:report:5",
            offer_actor_id="urn:test:submitter:5",
            offer_to=[actor_id],
        )
        result = _collect_create_case_addressees(
            actor=actor_id,
            report=None,
            offer_record=offer_record,
            actor_id=actor_id,
        )
        assert actor_id not in result

    def test_no_offer_record_returns_actor_only(self) -> None:
        """When offer_record is None, only actor is in addressee pool (self-excluded → empty)."""
        actor_id = "urn:test:actor:creator"
        result = _collect_create_case_addressees(
            actor=actor_id,
            report=None,
            offer_record=None,
            actor_id=actor_id,
        )
        assert actor_id not in result
