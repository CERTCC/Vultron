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
Service-layer unit tests for trigger service functions.

Tests call service functions directly (no HTTP layer) to verify domain
logic independently of the router layer.  Each service function accepts
a DataLayer instance as an argument rather than resolving it via
FastAPI's dependency injection.
"""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi._trigger_adapter import (
    close_report_trigger,
    defer_case_trigger,
    engage_case_trigger,
    evaluate_embargo_trigger,
    invalidate_report_trigger,
    propose_embargo_trigger,
    reject_report_trigger,
    terminate_embargo_trigger,
    validate_report_trigger,
)
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
        actor=actor.as_id,
        object=report.as_id,
        target=actor.as_id,
    )
    dl.create(offer_obj)
    return offer_obj


@pytest.fixture
def received_report(report):
    return report


@pytest.fixture
def accepted_report(report):
    return report


@pytest.fixture
def closed_report(dl, report, actor):
    status = VultronParticipantStatus(
        as_id=_report_phase_status_id(
            actor.as_id, report.as_id, RM.CLOSED.value
        ),
        context=report.as_id,
        attributed_to=actor.as_id,
        rm_state=RM.CLOSED,
    )
    dl.create(status)
    return report


@pytest.fixture
def case_with_participant(dl, actor):
    case_obj = VulnerabilityCase(name="TEST-CASE-001")
    participant = CaseParticipant(
        attributed_to=actor.as_id,
        context=case_obj.as_id,
    )
    # Pre-seed RM lifecycle so engage/defer (VALID→ACCEPTED/DEFERRED) are valid
    participant.append_rm_state(
        RM.RECEIVED, actor=actor.as_id, context=case_obj.as_id
    )
    participant.append_rm_state(
        RM.VALID, actor=actor.as_id, context=case_obj.as_id
    )
    case_obj.case_participants.append(participant.as_id)
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
    embargo = EmbargoEvent(context=case_obj.as_id)
    dl.create(embargo)
    case_obj.set_embargo(embargo.as_id)
    case_obj.current_status.em_state = EM.ACTIVE
    dl.create(case_obj)
    return case_obj, embargo


@pytest.fixture
def case_with_proposal(dl, actor):
    case_obj = VulnerabilityCase(name="PROPOSAL-CASE-001")
    embargo = EmbargoEvent(context=case_obj.as_id)
    dl.create(embargo)
    proposal = EmProposeEmbargoActivity(
        actor=actor.as_id,
        object=embargo.as_id,
        context=case_obj.as_id,
    )
    dl.create(proposal)
    case_obj.current_status.em_state = EM.PROPOSED
    case_obj.proposed_embargoes.append(embargo.as_id)
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
    result = validate_report_trigger(actor.as_id, offer.as_id, None, dl)
    assert isinstance(result, dict)
    assert "activity" in result


def test_validate_report_trigger_unknown_actor_raises_404(dl, offer):
    """validate_report_trigger raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        validate_report_trigger(
            "urn:uuid:no-such-actor", offer.as_id, None, dl
        )
    assert exc_info.value.status_code == 404


def test_validate_report_trigger_unknown_offer_raises_404(dl, actor):
    """validate_report_trigger raises HTTPException 404 for unknown offer."""
    with pytest.raises(HTTPException) as exc_info:
        validate_report_trigger(
            actor.as_id, "urn:uuid:no-such-offer", None, dl
        )
    assert exc_info.value.status_code == 404


def test_validate_report_trigger_adds_activity_to_outbox(
    dl, actor, offer, received_report
):
    """validate_report_trigger adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.as_id)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    validate_report_trigger(actor.as_id, offer.as_id, None, dl)

    actor_after = dl.read(actor.as_id)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1


def test_validate_report_trigger_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """validate_report_trigger raises 422 when offer_id is not a report Offer."""
    with pytest.raises(HTTPException) as exc_info:
        validate_report_trigger(actor.as_id, non_report_object.as_id, None, dl)
    assert exc_info.value.status_code == 422


# ===========================================================================
# invalidate_report_trigger
# ===========================================================================


def test_invalidate_report_trigger_returns_activity_dict(
    dl, actor, offer, received_report
):
    """invalidate_report_trigger returns dict with non-None 'activity'."""
    result = invalidate_report_trigger(actor.as_id, offer.as_id, None, dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_invalidate_report_trigger_unknown_actor_raises_404(dl, offer):
    """invalidate_report_trigger raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        invalidate_report_trigger("urn:uuid:no-such", offer.as_id, None, dl)
    assert exc_info.value.status_code == 404


def test_invalidate_report_trigger_unknown_offer_raises_404(dl, actor):
    """invalidate_report_trigger raises HTTPException 404 for unknown offer."""
    with pytest.raises(HTTPException) as exc_info:
        invalidate_report_trigger(actor.as_id, "urn:uuid:no-such", None, dl)
    assert exc_info.value.status_code == 404


def test_invalidate_report_trigger_adds_activity_to_outbox(
    dl, actor, offer, received_report
):
    """invalidate_report_trigger adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.as_id)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    invalidate_report_trigger(actor.as_id, offer.as_id, None, dl)

    actor_after = dl.read(actor.as_id)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1


def test_invalidate_report_trigger_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """invalidate_report_trigger raises 422 when offer_id is not a report Offer."""
    with pytest.raises(HTTPException) as exc_info:
        invalidate_report_trigger(
            actor.as_id, non_report_object.as_id, None, dl
        )
    assert exc_info.value.status_code == 422


# ===========================================================================
# reject_report_trigger
# ===========================================================================


def test_reject_report_trigger_returns_activity_dict(
    dl, actor, offer, received_report
):
    """reject_report_trigger returns dict with non-None 'activity'."""
    result = reject_report_trigger(
        actor.as_id, offer.as_id, "Out of scope.", dl
    )
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_reject_report_trigger_unknown_actor_raises_404(dl, offer):
    """reject_report_trigger raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        reject_report_trigger("urn:uuid:no-such", offer.as_id, "Reason.", dl)
    assert exc_info.value.status_code == 404


def test_reject_report_trigger_unknown_offer_raises_404(dl, actor):
    """reject_report_trigger raises HTTPException 404 for unknown offer."""
    with pytest.raises(HTTPException) as exc_info:
        reject_report_trigger(actor.as_id, "urn:uuid:no-such", "Reason.", dl)
    assert exc_info.value.status_code == 404


def test_reject_report_trigger_adds_activity_to_outbox(
    dl, actor, offer, received_report
):
    """reject_report_trigger adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.as_id)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    reject_report_trigger(actor.as_id, offer.as_id, "Reason.", dl)

    actor_after = dl.read(actor.as_id)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1


def test_reject_report_trigger_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """reject_report_trigger raises 422 when offer_id is not a report Offer."""
    with pytest.raises(HTTPException) as exc_info:
        reject_report_trigger(
            actor.as_id, non_report_object.as_id, "reason", dl
        )
    assert exc_info.value.status_code == 422


# ===========================================================================
# close_report_trigger
# ===========================================================================


def test_close_report_trigger_returns_activity_dict(
    dl, actor, offer, accepted_report
):
    """close_report_trigger returns dict with non-None 'activity'."""
    result = close_report_trigger(actor.as_id, offer.as_id, None, dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_close_report_trigger_already_closed_raises_409(
    dl, actor, offer, closed_report
):
    """close_report_trigger raises HTTPException 409 when report is CLOSED."""
    with pytest.raises(HTTPException) as exc_info:
        close_report_trigger(actor.as_id, offer.as_id, None, dl)
    assert exc_info.value.status_code == 409


def test_close_report_trigger_unknown_actor_raises_404(dl, offer):
    """close_report_trigger raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        close_report_trigger("urn:uuid:no-such", offer.as_id, None, dl)
    assert exc_info.value.status_code == 404


def test_close_report_trigger_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """close_report_trigger raises 422 when offer_id is not a report Offer."""
    with pytest.raises(HTTPException) as exc_info:
        close_report_trigger(actor.as_id, non_report_object.as_id, None, dl)
    assert exc_info.value.status_code == 422


# ===========================================================================
# engage_case_trigger
# ===========================================================================


def test_engage_case_trigger_returns_activity_dict(
    dl, actor, case_with_participant
):
    """engage_case_trigger returns dict with non-None 'activity'."""
    result = engage_case_trigger(actor.as_id, case_with_participant.as_id, dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_engage_case_trigger_unknown_actor_raises_404(
    dl, case_with_participant
):
    """engage_case_trigger raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        engage_case_trigger(
            "urn:uuid:no-such", case_with_participant.as_id, dl
        )
    assert exc_info.value.status_code == 404


def test_engage_case_trigger_unknown_case_raises_404(dl, actor):
    """engage_case_trigger raises HTTPException 404 for unknown case."""
    with pytest.raises(HTTPException) as exc_info:
        engage_case_trigger(actor.as_id, "urn:uuid:no-such-case", dl)
    assert exc_info.value.status_code == 404


def test_engage_case_trigger_invalid_case_id_raises_422(dl, actor):
    """engage_case_trigger raises 422 for a non-URI case_id."""
    with pytest.raises(HTTPException) as exc_info:
        engage_case_trigger(actor.as_id, "not-a-uri", dl)
    assert exc_info.value.status_code == 422


def test_engage_case_trigger_updates_participant_rm_state(
    dl, actor, case_with_participant
):
    """engage_case_trigger transitions actor's CaseParticipant RM state to ACCEPTED."""
    engage_case_trigger(actor.as_id, case_with_participant.as_id, dl)

    updated_case = dl.read(case_with_participant.as_id)
    for p_ref in updated_case.case_participants:
        p_id = p_ref if isinstance(p_ref, str) else p_ref.as_id
        p_obj = dl.read(p_id)
        if p_obj is None:
            continue
        actor_ref = p_obj.attributed_to
        p_actor_id = (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "as_id", str(actor_ref))
        )
        if p_actor_id == actor.as_id and p_obj.participant_statuses:
            assert p_obj.participant_statuses[-1].rm_state == RM.ACCEPTED
            return
    pytest.fail("Participant RM state was not updated to ACCEPTED")


def test_engage_case_trigger_adds_activity_to_outbox(
    dl, actor, case_with_participant
):
    """engage_case_trigger adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.as_id)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    engage_case_trigger(actor.as_id, case_with_participant.as_id, dl)

    actor_after = dl.read(actor.as_id)
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
    result = defer_case_trigger(actor.as_id, case_with_participant.as_id, dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_defer_case_trigger_unknown_actor_raises_404(
    dl, case_with_participant
):
    """defer_case_trigger raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        defer_case_trigger("urn:uuid:no-such", case_with_participant.as_id, dl)
    assert exc_info.value.status_code == 404


def test_defer_case_trigger_invalid_case_id_raises_422(dl, actor):
    """defer_case_trigger raises 422 for a non-URI case_id."""
    with pytest.raises(HTTPException) as exc_info:
        defer_case_trigger(actor.as_id, "not-a-uri", dl)
    assert exc_info.value.status_code == 422


def test_defer_case_trigger_updates_participant_rm_state(
    dl, actor, case_with_participant
):
    """defer_case_trigger transitions actor's CaseParticipant RM state to DEFERRED."""
    defer_case_trigger(actor.as_id, case_with_participant.as_id, dl)

    updated_case = dl.read(case_with_participant.as_id)
    for p_ref in updated_case.case_participants:
        p_id = p_ref if isinstance(p_ref, str) else p_ref.as_id
        p_obj = dl.read(p_id)
        if p_obj is None:
            continue
        actor_ref = p_obj.attributed_to
        p_actor_id = (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "as_id", str(actor_ref))
        )
        if p_actor_id == actor.as_id and p_obj.participant_statuses:
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
    result = propose_embargo_trigger(
        actor.as_id, case_no_participant.as_id, None, FUTURE_DATETIME, dl
    )
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_propose_embargo_trigger_transitions_em_state_to_proposed(
    dl, actor, case_no_participant
):
    """propose_embargo_trigger transitions case EM state from N to P."""
    propose_embargo_trigger(
        actor.as_id, case_no_participant.as_id, None, FUTURE_DATETIME, dl
    )
    updated = dl.read(case_no_participant.as_id)
    assert updated.current_status.em_state == EM.PROPOSED


def test_propose_embargo_trigger_exited_raises_409(
    dl, actor, case_no_participant
):
    """propose_embargo_trigger raises 409 when EM state is EXITED."""
    case_obj = dl.read(case_no_participant.as_id)
    case_obj.current_status.em_state = EM.EXITED
    dl.update(case_obj.as_id, object_to_record(case_obj))

    with pytest.raises(HTTPException) as exc_info:
        propose_embargo_trigger(
            actor.as_id, case_no_participant.as_id, None, FUTURE_DATETIME, dl
        )
    assert exc_info.value.status_code == 409


def test_propose_embargo_trigger_unknown_actor_raises_404(
    dl, case_no_participant
):
    """propose_embargo_trigger raises 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        propose_embargo_trigger(
            "urn:uuid:no-such",
            case_no_participant.as_id,
            None,
            FUTURE_DATETIME,
            dl,
        )
    assert exc_info.value.status_code == 404


def test_propose_embargo_trigger_naive_end_time_raises_422(
    dl, actor, case_no_participant
):
    """propose_embargo_trigger raises 422 for a timezone-naive end_time."""
    naive_dt = datetime(2099, 12, 1)
    with pytest.raises(HTTPException) as exc_info:
        propose_embargo_trigger(
            actor.as_id, case_no_participant.as_id, None, naive_dt, dl
        )
    assert exc_info.value.status_code == 422


def test_propose_embargo_trigger_past_end_time_raises_422(
    dl, actor, case_no_participant
):
    """propose_embargo_trigger raises 422 for a past end_time."""
    past_dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(HTTPException) as exc_info:
        propose_embargo_trigger(
            actor.as_id, case_no_participant.as_id, None, past_dt, dl
        )
    assert exc_info.value.status_code == 422


def test_propose_embargo_trigger_invalid_case_id_raises_422(dl, actor):
    """propose_embargo_trigger raises 422 for a non-URI case_id."""
    with pytest.raises(HTTPException) as exc_info:
        propose_embargo_trigger(
            actor.as_id, "not-a-uri", None, FUTURE_DATETIME, dl
        )
    assert exc_info.value.status_code == 422


# ===========================================================================
# evaluate_embargo_trigger
# ===========================================================================


def test_evaluate_embargo_trigger_returns_activity_dict(
    dl, actor, case_with_proposal
):
    """evaluate_embargo_trigger returns dict with non-None 'activity'."""
    case_obj, proposal, _ = case_with_proposal
    result = evaluate_embargo_trigger(
        actor.as_id, case_obj.as_id, proposal.as_id, dl
    )
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_evaluate_embargo_trigger_activates_embargo(
    dl, actor, case_with_proposal
):
    """evaluate_embargo_trigger sets EM state to ACTIVE."""
    case_obj, proposal, _ = case_with_proposal
    evaluate_embargo_trigger(actor.as_id, case_obj.as_id, proposal.as_id, dl)
    updated = dl.read(case_obj.as_id)
    assert updated.current_status.em_state == EM.ACTIVE
    assert updated.active_embargo is not None


def test_evaluate_embargo_trigger_without_proposal_id_finds_first(
    dl, actor, case_with_proposal
):
    """evaluate_embargo_trigger finds the first proposal when proposal_id is None."""
    case_obj, _, _ = case_with_proposal
    result = evaluate_embargo_trigger(actor.as_id, case_obj.as_id, None, dl)
    assert isinstance(result, dict)
    updated = dl.read(case_obj.as_id)
    assert updated.current_status.em_state == EM.ACTIVE


def test_evaluate_embargo_trigger_no_proposal_raises_404(
    dl, actor, case_no_participant
):
    """evaluate_embargo_trigger raises 404 when no proposal is found."""
    with pytest.raises(HTTPException) as exc_info:
        evaluate_embargo_trigger(
            actor.as_id, case_no_participant.as_id, None, dl
        )
    assert exc_info.value.status_code == 404


def test_evaluate_embargo_trigger_unknown_proposal_raises_404(
    dl, actor, case_no_participant
):
    """evaluate_embargo_trigger raises 404 when explicit proposal_id is not found."""
    with pytest.raises(HTTPException) as exc_info:
        evaluate_embargo_trigger(
            actor.as_id,
            case_no_participant.as_id,
            "urn:uuid:no-such-proposal",
            dl,
        )
    assert exc_info.value.status_code == 404


# ===========================================================================
# terminate_embargo_trigger
# ===========================================================================


def test_terminate_embargo_trigger_returns_activity_dict(
    dl, actor, case_with_embargo
):
    """terminate_embargo_trigger returns dict with non-None 'activity'."""
    case_obj, _ = case_with_embargo
    result = terminate_embargo_trigger(actor.as_id, case_obj.as_id, dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_terminate_embargo_trigger_sets_em_state_to_exited(
    dl, actor, case_with_embargo
):
    """terminate_embargo_trigger transitions case EM state to EXITED."""
    case_obj, _ = case_with_embargo
    terminate_embargo_trigger(actor.as_id, case_obj.as_id, dl)
    updated = dl.read(case_obj.as_id)
    assert updated.current_status.em_state == EM.EXITED


def test_terminate_embargo_trigger_clears_active_embargo(
    dl, actor, case_with_embargo
):
    """terminate_embargo_trigger clears active_embargo on the case."""
    case_obj, _ = case_with_embargo
    terminate_embargo_trigger(actor.as_id, case_obj.as_id, dl)
    updated = dl.read(case_obj.as_id)
    assert updated.active_embargo is None


def test_terminate_embargo_trigger_no_active_embargo_raises_409(
    dl, actor, case_no_participant
):
    """terminate_embargo_trigger raises 409 when no active embargo."""
    with pytest.raises(HTTPException) as exc_info:
        terminate_embargo_trigger(actor.as_id, case_no_participant.as_id, dl)
    assert exc_info.value.status_code == 409


def test_terminate_embargo_trigger_unknown_actor_raises_404(
    dl, case_with_embargo
):
    """terminate_embargo_trigger raises 404 for unknown actor."""
    case_obj, _ = case_with_embargo
    with pytest.raises(HTTPException) as exc_info:
        terminate_embargo_trigger("urn:uuid:no-such", case_obj.as_id, dl)
    assert exc_info.value.status_code == 404


def test_terminate_embargo_trigger_adds_activity_to_outbox(
    dl, actor, case_with_embargo
):
    """terminate_embargo_trigger adds a new activity to the actor's outbox."""
    case_obj, _ = case_with_embargo
    actor_before = dl.read(actor.as_id)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    terminate_embargo_trigger(actor.as_id, case_obj.as_id, dl)

    actor_after = dl.read(actor.as_id)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1
