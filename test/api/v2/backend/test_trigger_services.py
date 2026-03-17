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

FUTURE_DATETIME = datetime(2099, 12, 1, tzinfo=timezone.utc)

from vultron.adapters.driven.db_record import object_to_record
from vultron.api.v2.backend.trigger_services.case import (
    svc_defer_case,
    svc_engage_case,
)
from vultron.api.v2.backend.trigger_services.embargo import (
    svc_evaluate_embargo,
    svc_propose_embargo,
    svc_terminate_embargo,
)
from vultron.api.v2.backend.trigger_services.report import (
    svc_close_report,
    svc_invalidate_report,
    svc_reject_report,
    svc_validate_report,
)
from vultron.api.v2.data.actor_io import init_actor_io
from vultron.api.v2.data.status import ReportStatus, set_status
from vultron.bt.embargo_management.states import EM
from vultron.bt.report_management.states import RM
from vultron.wire.as2.vocab.activities.embargo import EmProposeEmbargoActivity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

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
    init_actor_io(actor_obj.as_id)
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
def received_report(report, actor):
    set_status(
        ReportStatus(
            object_type="VulnerabilityReport",
            object_id=report.as_id,
            actor_id=actor.as_id,
            status=RM.RECEIVED,
        )
    )
    return report


@pytest.fixture
def accepted_report(report, actor):
    set_status(
        ReportStatus(
            object_type="VulnerabilityReport",
            object_id=report.as_id,
            actor_id=actor.as_id,
            status=RM.ACCEPTED,
        )
    )
    return report


@pytest.fixture
def closed_report(report, actor):
    set_status(
        ReportStatus(
            object_type="VulnerabilityReport",
            object_id=report.as_id,
            actor_id=actor.as_id,
            status=RM.CLOSED,
        )
    )
    return report


@pytest.fixture
def case_with_participant(dl, actor):
    case_obj = VulnerabilityCase(name="TEST-CASE-001")
    participant = CaseParticipant(
        attributed_to=actor.as_id,
        context=case_obj.as_id,
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
# svc_validate_report
# ===========================================================================


def test_svc_validate_report_returns_activity_dict(
    dl, actor, offer, received_report
):
    """svc_validate_report returns dict with 'activity' key."""
    result = svc_validate_report(actor.as_id, offer.as_id, None, dl)
    assert isinstance(result, dict)
    assert "activity" in result


def test_svc_validate_report_unknown_actor_raises_404(dl, offer):
    """svc_validate_report raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        svc_validate_report("urn:uuid:no-such-actor", offer.as_id, None, dl)
    assert exc_info.value.status_code == 404


def test_svc_validate_report_unknown_offer_raises_404(dl, actor):
    """svc_validate_report raises HTTPException 404 for unknown offer."""
    with pytest.raises(HTTPException) as exc_info:
        svc_validate_report(actor.as_id, "urn:uuid:no-such-offer", None, dl)
    assert exc_info.value.status_code == 404


def test_svc_validate_report_adds_activity_to_outbox(
    dl, actor, offer, received_report
):
    """svc_validate_report adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.as_id)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    svc_validate_report(actor.as_id, offer.as_id, None, dl)

    actor_after = dl.read(actor.as_id)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1


def test_svc_validate_report_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """svc_validate_report raises 422 when offer_id is not a report Offer."""
    with pytest.raises(HTTPException) as exc_info:
        svc_validate_report(actor.as_id, non_report_object.as_id, None, dl)
    assert exc_info.value.status_code == 422


# ===========================================================================
# svc_invalidate_report
# ===========================================================================


def test_svc_invalidate_report_returns_activity_dict(
    dl, actor, offer, received_report
):
    """svc_invalidate_report returns dict with non-None 'activity'."""
    result = svc_invalidate_report(actor.as_id, offer.as_id, None, dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_svc_invalidate_report_unknown_actor_raises_404(dl, offer):
    """svc_invalidate_report raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        svc_invalidate_report("urn:uuid:no-such", offer.as_id, None, dl)
    assert exc_info.value.status_code == 404


def test_svc_invalidate_report_unknown_offer_raises_404(dl, actor):
    """svc_invalidate_report raises HTTPException 404 for unknown offer."""
    with pytest.raises(HTTPException) as exc_info:
        svc_invalidate_report(actor.as_id, "urn:uuid:no-such", None, dl)
    assert exc_info.value.status_code == 404


def test_svc_invalidate_report_adds_activity_to_outbox(
    dl, actor, offer, received_report
):
    """svc_invalidate_report adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.as_id)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    svc_invalidate_report(actor.as_id, offer.as_id, None, dl)

    actor_after = dl.read(actor.as_id)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1


def test_svc_invalidate_report_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """svc_invalidate_report raises 422 when offer_id is not a report Offer."""
    with pytest.raises(HTTPException) as exc_info:
        svc_invalidate_report(actor.as_id, non_report_object.as_id, None, dl)
    assert exc_info.value.status_code == 422


# ===========================================================================
# svc_reject_report
# ===========================================================================


def test_svc_reject_report_returns_activity_dict(
    dl, actor, offer, received_report
):
    """svc_reject_report returns dict with non-None 'activity'."""
    result = svc_reject_report(actor.as_id, offer.as_id, "Out of scope.", dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_svc_reject_report_unknown_actor_raises_404(dl, offer):
    """svc_reject_report raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        svc_reject_report("urn:uuid:no-such", offer.as_id, "Reason.", dl)
    assert exc_info.value.status_code == 404


def test_svc_reject_report_unknown_offer_raises_404(dl, actor):
    """svc_reject_report raises HTTPException 404 for unknown offer."""
    with pytest.raises(HTTPException) as exc_info:
        svc_reject_report(actor.as_id, "urn:uuid:no-such", "Reason.", dl)
    assert exc_info.value.status_code == 404


def test_svc_reject_report_adds_activity_to_outbox(
    dl, actor, offer, received_report
):
    """svc_reject_report adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.as_id)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    svc_reject_report(actor.as_id, offer.as_id, "Reason.", dl)

    actor_after = dl.read(actor.as_id)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1


def test_svc_reject_report_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """svc_reject_report raises 422 when offer_id is not a report Offer."""
    with pytest.raises(HTTPException) as exc_info:
        svc_reject_report(actor.as_id, non_report_object.as_id, "reason", dl)
    assert exc_info.value.status_code == 422


# ===========================================================================
# svc_close_report
# ===========================================================================


def test_svc_close_report_returns_activity_dict(
    dl, actor, offer, accepted_report
):
    """svc_close_report returns dict with non-None 'activity'."""
    result = svc_close_report(actor.as_id, offer.as_id, None, dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_svc_close_report_already_closed_raises_409(
    dl, actor, offer, closed_report
):
    """svc_close_report raises HTTPException 409 when report is CLOSED."""
    with pytest.raises(HTTPException) as exc_info:
        svc_close_report(actor.as_id, offer.as_id, None, dl)
    assert exc_info.value.status_code == 409


def test_svc_close_report_unknown_actor_raises_404(dl, offer):
    """svc_close_report raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        svc_close_report("urn:uuid:no-such", offer.as_id, None, dl)
    assert exc_info.value.status_code == 404


def test_svc_close_report_non_report_offer_raises_422(
    dl, actor, non_report_object
):
    """svc_close_report raises 422 when offer_id is not a report Offer."""
    with pytest.raises(HTTPException) as exc_info:
        svc_close_report(actor.as_id, non_report_object.as_id, None, dl)
    assert exc_info.value.status_code == 422


# ===========================================================================
# svc_engage_case
# ===========================================================================


def test_svc_engage_case_returns_activity_dict(
    dl, actor, case_with_participant
):
    """svc_engage_case returns dict with non-None 'activity'."""
    result = svc_engage_case(actor.as_id, case_with_participant.as_id, dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_svc_engage_case_unknown_actor_raises_404(dl, case_with_participant):
    """svc_engage_case raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        svc_engage_case("urn:uuid:no-such", case_with_participant.as_id, dl)
    assert exc_info.value.status_code == 404


def test_svc_engage_case_unknown_case_raises_404(dl, actor):
    """svc_engage_case raises HTTPException 404 for unknown case."""
    with pytest.raises(HTTPException) as exc_info:
        svc_engage_case(actor.as_id, "urn:uuid:no-such-case", dl)
    assert exc_info.value.status_code == 404


def test_svc_engage_case_invalid_case_id_raises_422(dl, actor):
    """svc_engage_case raises 422 for a non-URI case_id."""
    with pytest.raises(HTTPException) as exc_info:
        svc_engage_case(actor.as_id, "not-a-uri", dl)
    assert exc_info.value.status_code == 422


def test_svc_engage_case_updates_participant_rm_state(
    dl, actor, case_with_participant
):
    """svc_engage_case transitions actor's CaseParticipant RM state to ACCEPTED."""
    svc_engage_case(actor.as_id, case_with_participant.as_id, dl)

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


def test_svc_engage_case_adds_activity_to_outbox(
    dl, actor, case_with_participant
):
    """svc_engage_case adds a new activity to the actor's outbox."""
    actor_before = dl.read(actor.as_id)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    svc_engage_case(actor.as_id, case_with_participant.as_id, dl)

    actor_after = dl.read(actor.as_id)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1


# ===========================================================================
# svc_defer_case
# ===========================================================================


def test_svc_defer_case_returns_activity_dict(
    dl, actor, case_with_participant
):
    """svc_defer_case returns dict with non-None 'activity'."""
    result = svc_defer_case(actor.as_id, case_with_participant.as_id, dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_svc_defer_case_unknown_actor_raises_404(dl, case_with_participant):
    """svc_defer_case raises HTTPException 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        svc_defer_case("urn:uuid:no-such", case_with_participant.as_id, dl)
    assert exc_info.value.status_code == 404


def test_svc_defer_case_invalid_case_id_raises_422(dl, actor):
    """svc_defer_case raises 422 for a non-URI case_id."""
    with pytest.raises(HTTPException) as exc_info:
        svc_defer_case(actor.as_id, "not-a-uri", dl)
    assert exc_info.value.status_code == 422


def test_svc_defer_case_updates_participant_rm_state(
    dl, actor, case_with_participant
):
    """svc_defer_case transitions actor's CaseParticipant RM state to DEFERRED."""
    svc_defer_case(actor.as_id, case_with_participant.as_id, dl)

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
# svc_propose_embargo
# ===========================================================================


def test_svc_propose_embargo_returns_activity_dict(
    dl, actor, case_no_participant
):
    """svc_propose_embargo returns dict with non-None 'activity'."""
    result = svc_propose_embargo(
        actor.as_id, case_no_participant.as_id, None, FUTURE_DATETIME, dl
    )
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_svc_propose_embargo_transitions_em_state_to_proposed(
    dl, actor, case_no_participant
):
    """svc_propose_embargo transitions case EM state from N to P."""
    svc_propose_embargo(
        actor.as_id, case_no_participant.as_id, None, FUTURE_DATETIME, dl
    )
    updated = dl.read(case_no_participant.as_id)
    assert updated.current_status.em_state == EM.PROPOSED


def test_svc_propose_embargo_exited_raises_409(dl, actor, case_no_participant):
    """svc_propose_embargo raises 409 when EM state is EXITED."""
    case_obj = dl.read(case_no_participant.as_id)
    case_obj.current_status.em_state = EM.EXITED
    dl.update(case_obj.as_id, object_to_record(case_obj))

    with pytest.raises(HTTPException) as exc_info:
        svc_propose_embargo(
            actor.as_id, case_no_participant.as_id, None, FUTURE_DATETIME, dl
        )
    assert exc_info.value.status_code == 409


def test_svc_propose_embargo_unknown_actor_raises_404(dl, case_no_participant):
    """svc_propose_embargo raises 404 for unknown actor."""
    with pytest.raises(HTTPException) as exc_info:
        svc_propose_embargo(
            "urn:uuid:no-such",
            case_no_participant.as_id,
            None,
            FUTURE_DATETIME,
            dl,
        )
    assert exc_info.value.status_code == 404


def test_svc_propose_embargo_naive_end_time_raises_422(
    dl, actor, case_no_participant
):
    """svc_propose_embargo raises 422 for a timezone-naive end_time."""
    naive_dt = datetime(2099, 12, 1)
    with pytest.raises(HTTPException) as exc_info:
        svc_propose_embargo(
            actor.as_id, case_no_participant.as_id, None, naive_dt, dl
        )
    assert exc_info.value.status_code == 422


def test_svc_propose_embargo_past_end_time_raises_422(
    dl, actor, case_no_participant
):
    """svc_propose_embargo raises 422 for a past end_time."""
    past_dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(HTTPException) as exc_info:
        svc_propose_embargo(
            actor.as_id, case_no_participant.as_id, None, past_dt, dl
        )
    assert exc_info.value.status_code == 422


def test_svc_propose_embargo_invalid_case_id_raises_422(dl, actor):
    """svc_propose_embargo raises 422 for a non-URI case_id."""
    with pytest.raises(HTTPException) as exc_info:
        svc_propose_embargo(
            actor.as_id, "not-a-uri", None, FUTURE_DATETIME, dl
        )
    assert exc_info.value.status_code == 422


# ===========================================================================
# svc_evaluate_embargo
# ===========================================================================


def test_svc_evaluate_embargo_returns_activity_dict(
    dl, actor, case_with_proposal
):
    """svc_evaluate_embargo returns dict with non-None 'activity'."""
    case_obj, proposal, _ = case_with_proposal
    result = svc_evaluate_embargo(
        actor.as_id, case_obj.as_id, proposal.as_id, dl
    )
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_svc_evaluate_embargo_activates_embargo(dl, actor, case_with_proposal):
    """svc_evaluate_embargo sets EM state to ACTIVE."""
    case_obj, proposal, _ = case_with_proposal
    svc_evaluate_embargo(actor.as_id, case_obj.as_id, proposal.as_id, dl)
    updated = dl.read(case_obj.as_id)
    assert updated.current_status.em_state == EM.ACTIVE
    assert updated.active_embargo is not None


def test_svc_evaluate_embargo_without_proposal_id_finds_first(
    dl, actor, case_with_proposal
):
    """svc_evaluate_embargo finds the first proposal when proposal_id is None."""
    case_obj, _, _ = case_with_proposal
    result = svc_evaluate_embargo(actor.as_id, case_obj.as_id, None, dl)
    assert isinstance(result, dict)
    updated = dl.read(case_obj.as_id)
    assert updated.current_status.em_state == EM.ACTIVE


def test_svc_evaluate_embargo_no_proposal_raises_404(
    dl, actor, case_no_participant
):
    """svc_evaluate_embargo raises 404 when no proposal is found."""
    with pytest.raises(HTTPException) as exc_info:
        svc_evaluate_embargo(actor.as_id, case_no_participant.as_id, None, dl)
    assert exc_info.value.status_code == 404


def test_svc_evaluate_embargo_unknown_proposal_raises_404(
    dl, actor, case_no_participant
):
    """svc_evaluate_embargo raises 404 when explicit proposal_id is not found."""
    with pytest.raises(HTTPException) as exc_info:
        svc_evaluate_embargo(
            actor.as_id,
            case_no_participant.as_id,
            "urn:uuid:no-such-proposal",
            dl,
        )
    assert exc_info.value.status_code == 404


# ===========================================================================
# svc_terminate_embargo
# ===========================================================================


def test_svc_terminate_embargo_returns_activity_dict(
    dl, actor, case_with_embargo
):
    """svc_terminate_embargo returns dict with non-None 'activity'."""
    case_obj, _ = case_with_embargo
    result = svc_terminate_embargo(actor.as_id, case_obj.as_id, dl)
    assert isinstance(result, dict)
    assert result["activity"] is not None


def test_svc_terminate_embargo_sets_em_state_to_exited(
    dl, actor, case_with_embargo
):
    """svc_terminate_embargo transitions case EM state to EXITED."""
    case_obj, _ = case_with_embargo
    svc_terminate_embargo(actor.as_id, case_obj.as_id, dl)
    updated = dl.read(case_obj.as_id)
    assert updated.current_status.em_state == EM.EXITED


def test_svc_terminate_embargo_clears_active_embargo(
    dl, actor, case_with_embargo
):
    """svc_terminate_embargo clears active_embargo on the case."""
    case_obj, _ = case_with_embargo
    svc_terminate_embargo(actor.as_id, case_obj.as_id, dl)
    updated = dl.read(case_obj.as_id)
    assert updated.active_embargo is None


def test_svc_terminate_embargo_no_active_embargo_raises_409(
    dl, actor, case_no_participant
):
    """svc_terminate_embargo raises 409 when no active embargo."""
    with pytest.raises(HTTPException) as exc_info:
        svc_terminate_embargo(actor.as_id, case_no_participant.as_id, dl)
    assert exc_info.value.status_code == 409


def test_svc_terminate_embargo_unknown_actor_raises_404(dl, case_with_embargo):
    """svc_terminate_embargo raises 404 for unknown actor."""
    case_obj, _ = case_with_embargo
    with pytest.raises(HTTPException) as exc_info:
        svc_terminate_embargo("urn:uuid:no-such", case_obj.as_id, dl)
    assert exc_info.value.status_code == 404


def test_svc_terminate_embargo_adds_activity_to_outbox(
    dl, actor, case_with_embargo
):
    """svc_terminate_embargo adds a new activity to the actor's outbox."""
    case_obj, _ = case_with_embargo
    actor_before = dl.read(actor.as_id)
    before = {
        item for item in actor_before.outbox.items if isinstance(item, str)
    }

    svc_terminate_embargo(actor.as_id, case_obj.as_id, dl)

    actor_after = dl.read(actor.as_id)
    after = {
        item for item in actor_after.outbox.items if isinstance(item, str)
    }
    assert len(after - before) >= 1
