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

"""Service-layer unit tests for ``TriggerService``.

Tests call :class:`~vultron.core.use_cases.triggers.service.TriggerService`
directly (no HTTP layer) to verify domain behavior independently of the
FastAPI adapter layer.
"""

from datetime import datetime, timezone

import pytest

from vultron.adapters.driven.db_record import object_to_record
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.core.use_cases.triggers.service import TriggerService

try:
    from pydantic import ValidationError as PydanticValidationError
except ImportError:
    from pydantic_core import ValidationError as PydanticValidationError
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.use_cases._helpers import _report_phase_status_id
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.activities.embargo import EmProposeEmbargoActivity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

FUTURE_DATETIME = datetime(2099, 12, 1, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dl(datalayer):
    return datalayer


@pytest.fixture
def actor(dl):
    actor_obj = as_Service(name="Vendor Co")
    dl.create(object_to_record(actor_obj))
    return actor_obj


@pytest.fixture
def report(dl):
    report_obj = VulnerabilityReport(
        name="Test Vulnerability",
        content="Test content",
    )
    dl.create(report_obj)
    return report_obj


@pytest.fixture
def offer(dl, report, actor):
    offer_obj = as_Offer(
        actor=actor.id_,
        object_=report.id_,
        target=actor.id_,
    )
    dl.create(offer_obj)
    return offer_obj


@pytest.fixture
def received_report(dl, actor, report, offer):
    """Pre-create a VulnerabilityCase for the report at RM.RECEIVED.

    Per ADR-0015, the case is created at report receipt.  The validate_report
    BT's EnsureEmbargoExists node requires a case to exist.
    """
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.receive_report_case_tree import (
        create_receive_report_case_tree,
    )

    bridge = BTBridge(datalayer=dl)
    tree = create_receive_report_case_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        reporter_actor_id=actor.id_,
    )
    bridge.execute_with_setup(tree, actor_id=actor.id_)
    return report


@pytest.fixture
def accepted_report(report):
    return report


@pytest.fixture
def closed_report(dl, report, actor):
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.CLOSED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.CLOSED,
    )
    dl.create(status)
    return report


@pytest.fixture
def case_with_participant(dl, actor):
    case_obj = VulnerabilityCase(name="TEST-CASE-001")
    participant = CaseParticipant(
        attributed_to=actor.id_,
        context=case_obj.id_,
    )
    # Pre-seed RM lifecycle so engage/defer (VALID→ACCEPTED/DEFERRED) are valid
    participant.append_rm_state(
        RM.RECEIVED, actor=actor.id_, context=case_obj.id_
    )
    participant.append_rm_state(
        RM.VALID, actor=actor.id_, context=case_obj.id_
    )
    case_obj.case_participants.append(participant.id_)
    dl.create(case_obj)
    dl.create(participant)
    return case_obj


@pytest.fixture
def case_no_participant(dl):
    case_obj = VulnerabilityCase(name="TEST-CASE-NO-P")
    dl.create(case_obj)
    return case_obj


@pytest.fixture
def case_with_embargo(dl, actor):
    case_obj = VulnerabilityCase(name="EMBARGO-CASE-001")
    embargo = EmbargoEvent(context=case_obj.id_)
    dl.create(embargo)
    case_obj.set_embargo(embargo.id_)
    case_obj.current_status.em_state = EM.ACTIVE
    dl.create(case_obj)
    return case_obj, embargo


@pytest.fixture
def case_with_proposal(dl, actor):
    case_obj = VulnerabilityCase(name="PROPOSAL-CASE-001")
    embargo = EmbargoEvent(context=case_obj.id_)
    dl.create(embargo)
    proposal = EmProposeEmbargoActivity(
        actor=actor.id_,
        object_=embargo,
        context=case_obj.id_,
    )
    dl.create(proposal)
    case_obj.current_status.em_state = EM.PROPOSED
    case_obj.proposed_embargoes.append(embargo.id_)
    dl.create(case_obj)
    return case_obj, proposal, embargo


@pytest.fixture
def non_report_object(dl):
    """An EmbargoEvent stored in the datalayer — not an Offer."""
    obj = EmbargoEvent(context="urn:uuid:some-case")
    dl.create(obj)
    return obj


# ===========================================================================
# validate_report_trigger
# ===========================================================================


def test_validate_report_trigger_returns_activity_dict(
    dl, actor, offer, received_report
):
    """validate_report_trigger returns dict with 'activity' key."""
    result = TriggerService(dl).validate_report(actor.id_, offer.id_, None)
    assert isinstance(result, dict)
    assert "activity" in result


def test_validate_report_trigger_unknown_actor_raises_404(dl, offer):
    """validate_report_trigger raises VultronNotFoundError 404 for unknown actor."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).validate_report(
            "urn:uuid:no-such-actor", offer.id_, None
        )


def test_validate_report_trigger_unknown_offer_raises_404(dl, actor):
    """validate_report_trigger raises VultronNotFoundError 404 for unknown offer."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).validate_report(
            actor.id_, "urn:uuid:no-such-offer", None
        )


def test_validate_report_trigger_transitions_rm_to_valid(
    dl, actor, offer, received_report
):
    """validate_report_trigger transitions RM state to VALID.

    Per ADR-0015, case creation (and outbox notifications) now happen at
    RM.RECEIVED via receive_report_case_tree.  The validate-report trigger
    is responsible only for the RM.RECEIVED → RM.VALID transition.
    """
    TriggerService(dl).validate_report(actor.id_, offer.id_, None)

    valid_status_id = _report_phase_status_id(
        actor.id_, offer.object_, RM.VALID.value
    )
    valid_record = dl.get("ParticipantStatus", valid_status_id)
    assert (
        valid_record is not None
    ), "Expected a RM.VALID ParticipantStatus after validate_report_trigger"


def test_validate_report_trigger_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """validate_report_trigger raises 422 when offer_id is not a report Offer."""
    with pytest.raises(VultronValidationError):
        TriggerService(dl).validate_report(
            actor.id_, non_report_object.id_, None
        )


# ===========================================================================
# invalidate_report_trigger
# ===========================================================================


def test_invalidate_report_trigger_returns_activity_dict(
    dl, actor, offer, received_report
):
    """invalidate_report_trigger returns dict with non-None 'activity'."""
    result = TriggerService(dl).invalidate_report(actor.id_, offer.id_, None)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_invalidate_report_trigger_unknown_actor_raises_404(dl, offer):
    """invalidate_report_trigger raises VultronNotFoundError 404 for unknown actor."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).invalidate_report(
            "urn:uuid:no-such", offer.id_, None
        )


def test_invalidate_report_trigger_unknown_offer_raises_404(dl, actor):
    """invalidate_report_trigger raises VultronNotFoundError 404 for unknown offer."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).invalidate_report(
            actor.id_, "urn:uuid:no-such", None
        )


def test_invalidate_report_trigger_adds_activity_to_outbox(
    dl, actor, offer, received_report
):
    """invalidate_report_trigger adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.id_)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    TriggerService(dl).invalidate_report(actor.id_, offer.id_, None)

    actor_after = dl.read(actor.id_)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1


def test_invalidate_report_trigger_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """invalidate_report_trigger raises 422 when offer_id is not a report Offer."""
    with pytest.raises(VultronValidationError):
        TriggerService(dl).invalidate_report(
            actor.id_, non_report_object.id_, None
        )


# ===========================================================================
# reject_report_trigger
# ===========================================================================


def test_reject_report_trigger_returns_activity_dict(
    dl, actor, offer, received_report
):
    """reject_report_trigger returns dict with non-None 'activity'."""
    result = TriggerService(dl).reject_report(
        actor.id_, offer.id_, "Out of scope."
    )
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_reject_report_trigger_unknown_actor_raises_404(dl, offer):
    """reject_report_trigger raises VultronNotFoundError 404 for unknown actor."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).reject_report(
            "urn:uuid:no-such", offer.id_, "Reason."
        )


def test_reject_report_trigger_unknown_offer_raises_404(dl, actor):
    """reject_report_trigger raises VultronNotFoundError 404 for unknown offer."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).reject_report(
            actor.id_, "urn:uuid:no-such", "Reason."
        )


def test_reject_report_trigger_adds_activity_to_outbox(
    dl, actor, offer, received_report
):
    """reject_report_trigger adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.id_)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    TriggerService(dl).reject_report(actor.id_, offer.id_, "Reason.")

    actor_after = dl.read(actor.id_)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1


def test_reject_report_trigger_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """reject_report_trigger raises 422 when offer_id is not a report Offer."""
    with pytest.raises(VultronValidationError):
        TriggerService(dl).reject_report(
            actor.id_, non_report_object.id_, "reason"
        )


# ===========================================================================
# close_report_trigger
# ===========================================================================


def test_close_report_trigger_returns_activity_dict(
    dl, actor, offer, accepted_report
):
    """close_report_trigger returns dict with non-None 'activity'."""
    result = TriggerService(dl).close_report(actor.id_, offer.id_, None)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_close_report_trigger_already_closed_raises_409(
    dl, actor, offer, closed_report
):
    """close_report_trigger raises VultronInvalidStateTransitionError when report is CLOSED."""
    with pytest.raises(VultronInvalidStateTransitionError):
        TriggerService(dl).close_report(actor.id_, offer.id_, None)


def test_close_report_trigger_unknown_actor_raises_404(dl, offer):
    """close_report_trigger raises VultronNotFoundError 404 for unknown actor."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).close_report("urn:uuid:no-such", offer.id_, None)


def test_close_report_trigger_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """close_report_trigger raises 422 when offer_id is not a report Offer."""
    with pytest.raises(VultronValidationError):
        TriggerService(dl).close_report(actor.id_, non_report_object.id_, None)


# ===========================================================================
# engage_case_trigger
# ===========================================================================


def test_engage_case_trigger_returns_activity_dict(
    dl, actor, case_with_participant
):
    """engage_case_trigger returns dict with non-None 'activity'."""
    result = TriggerService(dl).engage_case(
        actor.id_, case_with_participant.id_
    )
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_engage_case_trigger_unknown_actor_raises_404(
    dl, case_with_participant
):
    """engage_case_trigger raises VultronNotFoundError 404 for unknown actor."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).engage_case(
            "urn:uuid:no-such", case_with_participant.id_
        )


def test_engage_case_trigger_unknown_case_raises_404(dl, actor):
    """engage_case_trigger raises VultronNotFoundError 404 for unknown case."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).engage_case(actor.id_, "urn:uuid:no-such-case")


def test_engage_case_trigger_invalid_case_id_raises_422(dl, actor):
    """engage_case_trigger raises PydanticValidationError for a non-URI case_id."""
    with pytest.raises(PydanticValidationError):
        TriggerService(dl).engage_case(actor.id_, "not-a-uri")


def test_engage_case_trigger_updates_participant_rm_state(
    dl, actor, case_with_participant
):
    """engage_case_trigger transitions actor's CaseParticipant RM state to ACCEPTED."""
    TriggerService(dl).engage_case(actor.id_, case_with_participant.id_)

    updated_case = dl.read(case_with_participant.id_)
    for p_ref in updated_case.case_participants:
        p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
        p_obj = dl.read(p_id)
        if p_obj is None:
            continue
        actor_ref = p_obj.attributed_to
        p_actor_id = (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "id_", str(actor_ref))
        )
        if p_actor_id == actor.id_ and p_obj.participant_statuses:
            assert p_obj.participant_statuses[-1].rm_state == RM.ACCEPTED
            return
    pytest.fail("Participant RM state was not updated to ACCEPTED")


def test_engage_case_trigger_adds_activity_to_outbox(
    dl, actor, case_with_participant
):
    """engage_case_trigger adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.id_)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    TriggerService(dl).engage_case(actor.id_, case_with_participant.id_)

    actor_after = dl.read(actor.id_)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1


# ===========================================================================
# defer_case_trigger
# ===========================================================================


def test_defer_case_trigger_returns_activity_dict(
    dl, actor, case_with_participant
):
    """defer_case_trigger returns dict with non-None 'activity'."""
    result = TriggerService(dl).defer_case(
        actor.id_, case_with_participant.id_
    )
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_defer_case_trigger_unknown_actor_raises_404(
    dl, case_with_participant
):
    """defer_case_trigger raises VultronNotFoundError 404 for unknown actor."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).defer_case(
            "urn:uuid:no-such", case_with_participant.id_
        )


def test_defer_case_trigger_invalid_case_id_raises_422(dl, actor):
    """defer_case_trigger raises PydanticValidationError for a non-URI case_id."""
    with pytest.raises(PydanticValidationError):
        TriggerService(dl).defer_case(actor.id_, "not-a-uri")


def test_defer_case_trigger_updates_participant_rm_state(
    dl, actor, case_with_participant
):
    """defer_case_trigger transitions actor's CaseParticipant RM state to DEFERRED."""
    TriggerService(dl).defer_case(actor.id_, case_with_participant.id_)

    updated_case = dl.read(case_with_participant.id_)
    for p_ref in updated_case.case_participants:
        p_id = p_ref if isinstance(p_ref, str) else p_ref.id_
        p_obj = dl.read(p_id)
        if p_obj is None:
            continue
        actor_ref = p_obj.attributed_to
        p_actor_id = (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "id_", str(actor_ref))
        )
        if p_actor_id == actor.id_ and p_obj.participant_statuses:
            assert p_obj.participant_statuses[-1].rm_state == RM.DEFERRED
            return
    pytest.fail("Participant RM state was not updated to DEFERRED")


# ===========================================================================
# propose_embargo_trigger
# ===========================================================================


def test_propose_embargo_trigger_returns_activity_dict(
    dl, actor, case_no_participant
):
    """propose_embargo_trigger returns dict with non-None 'activity'."""
    result = TriggerService(dl).propose_embargo(
        actor.id_, case_no_participant.id_, FUTURE_DATETIME
    )
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_propose_embargo_trigger_transitions_em_state_to_proposed(
    dl, actor, case_no_participant
):
    """propose_embargo_trigger transitions case EM state from N to P."""
    TriggerService(dl).propose_embargo(
        actor.id_, case_no_participant.id_, FUTURE_DATETIME
    )
    updated = dl.read(case_no_participant.id_)
    assert updated.current_status.em_state == EM.PROPOSED


def test_propose_embargo_trigger_exited_raises_409(
    dl, actor, case_no_participant
):
    """propose_embargo_trigger raises 409 when EM state is EXITED."""
    case_obj = dl.read(case_no_participant.id_)
    case_obj.current_status.em_state = EM.EXITED
    dl.update(case_obj.id_, object_to_record(case_obj))

    with pytest.raises(VultronInvalidStateTransitionError):
        TriggerService(dl).propose_embargo(
            actor.id_, case_no_participant.id_, FUTURE_DATETIME
        )


def test_propose_embargo_trigger_unknown_actor_raises_404(
    dl, case_no_participant
):
    """propose_embargo_trigger raises 404 for unknown actor."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).propose_embargo(
            "urn:uuid:no-such",
            case_no_participant.id_,
            FUTURE_DATETIME,
        )


def test_propose_embargo_trigger_naive_end_time_raises_422(
    dl, actor, case_no_participant
):
    """propose_embargo_trigger raises PydanticValidationError for a timezone-naive end_time."""
    naive_dt = datetime(2099, 12, 1)
    with pytest.raises(PydanticValidationError):
        TriggerService(dl).propose_embargo(
            actor.id_, case_no_participant.id_, naive_dt
        )


def test_propose_embargo_trigger_past_end_time_raises_422(
    dl, actor, case_no_participant
):
    """propose_embargo_trigger raises PydanticValidationError for a past end_time."""
    past_dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(PydanticValidationError):
        TriggerService(dl).propose_embargo(
            actor.id_, case_no_participant.id_, past_dt
        )


def test_propose_embargo_trigger_invalid_case_id_raises_422(dl, actor):
    """propose_embargo_trigger raises PydanticValidationError for a non-URI case_id."""
    with pytest.raises(PydanticValidationError):
        TriggerService(dl).propose_embargo(
            actor.id_, "not-a-uri", FUTURE_DATETIME
        )


# ===========================================================================
# evaluate_embargo_trigger
# ===========================================================================


def test_evaluate_embargo_trigger_returns_activity_dict(
    dl, actor, case_with_proposal
):
    """evaluate_embargo_trigger returns dict with non-None 'activity'."""
    case_obj, proposal, _ = case_with_proposal
    result = TriggerService(dl).accept_embargo(
        actor.id_, case_obj.id_, proposal.id_
    )
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_evaluate_embargo_trigger_activates_embargo(
    dl, actor, case_with_proposal
):
    """evaluate_embargo_trigger sets EM state to ACTIVE."""
    case_obj, proposal, _ = case_with_proposal
    TriggerService(dl).accept_embargo(actor.id_, case_obj.id_, proposal.id_)
    updated = dl.read(case_obj.id_)
    assert updated.current_status.em_state == EM.ACTIVE
    assert updated.active_embargo is not None


def test_evaluate_embargo_trigger_without_proposal_id_finds_first(
    dl, actor, case_with_proposal
):
    """evaluate_embargo_trigger finds the first proposal when proposal_id is None."""
    case_obj, _, _ = case_with_proposal
    result = TriggerService(dl).accept_embargo(actor.id_, case_obj.id_, None)
    assert isinstance(result, dict)
    updated = dl.read(case_obj.id_)
    assert updated.current_status.em_state == EM.ACTIVE


def test_evaluate_embargo_trigger_no_proposal_raises_404(
    dl, actor, case_no_participant
):
    """evaluate_embargo_trigger raises 404 when no proposal is found."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).accept_embargo(
            actor.id_, case_no_participant.id_, None
        )


def test_evaluate_embargo_trigger_unknown_proposal_raises_404(
    dl, actor, case_no_participant
):
    """evaluate_embargo_trigger raises 404 when explicit proposal_id is not found."""
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).accept_embargo(
            actor.id_,
            case_no_participant.id_,
            "urn:uuid:no-such-proposal",
        )


# ===========================================================================
# terminate_embargo_trigger
# ===========================================================================


def test_terminate_embargo_trigger_returns_activity_dict(
    dl, actor, case_with_embargo
):
    """terminate_embargo_trigger returns dict with non-None 'activity'."""
    case_obj, _ = case_with_embargo
    result = TriggerService(dl).terminate_embargo(actor.id_, case_obj.id_)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_terminate_embargo_trigger_sets_em_state_to_exited(
    dl, actor, case_with_embargo
):
    """terminate_embargo_trigger transitions case EM state to EXITED."""
    case_obj, _ = case_with_embargo
    TriggerService(dl).terminate_embargo(actor.id_, case_obj.id_)
    updated = dl.read(case_obj.id_)
    assert updated.current_status.em_state == EM.EXITED


def test_terminate_embargo_trigger_clears_active_embargo(
    dl, actor, case_with_embargo
):
    """terminate_embargo_trigger clears active_embargo on the case."""
    case_obj, _ = case_with_embargo
    TriggerService(dl).terminate_embargo(actor.id_, case_obj.id_)
    updated = dl.read(case_obj.id_)
    assert updated.active_embargo is None


def test_terminate_embargo_trigger_no_active_embargo_raises_409(
    dl, actor, case_no_participant
):
    """terminate_embargo_trigger raises 409 when no active embargo."""
    with pytest.raises(VultronInvalidStateTransitionError):
        TriggerService(dl).terminate_embargo(
            actor.id_, case_no_participant.id_
        )


def test_terminate_embargo_trigger_unknown_actor_raises_404(
    dl, case_with_embargo
):
    """terminate_embargo_trigger raises 404 for unknown actor."""
    case_obj, _ = case_with_embargo
    with pytest.raises(VultronNotFoundError):
        TriggerService(dl).terminate_embargo("urn:uuid:no-such", case_obj.id_)


def test_terminate_embargo_trigger_adds_activity_to_outbox(
    dl, actor, case_with_embargo
):
    """terminate_embargo_trigger adds a new activity to the actor's outbox."""
    case_obj, _ = case_with_embargo
    actor_before = dl.read(actor.id_)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    TriggerService(dl).terminate_embargo(actor.id_, case_obj.id_)

    actor_after = dl.read(actor.id_)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1
