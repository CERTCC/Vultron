"""Chain-level integration test: SubmitReport → ValidateReport → EngageCase.

Verifies that the three-step handoff produces the correct RM state sequence
(START → RECEIVED → VALID → ACCEPTED) against a single in-memory DataLayer.
No demo infrastructure or CI devlogs required.

The fixture pre-seeds the case+offer+report in the vendor's DataLayer, mirroring
the setup used in test_report_triggers.py (the vendor's inbox already has the
offer + linked case after receiving a SubmitReport from the finder).

AC-3 of ISSUE-1976.
"""

from __future__ import annotations

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.core.use_cases.triggers.case import (
    EngageCaseTriggerRequest,
    SvcEngageCaseUseCase,
)
from vultron.core.use_cases.triggers.report import (
    SvcValidateReportUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    ValidateReportTriggerRequest,
)
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderParticipant,
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import (
    as_ParticipantStatus as WireParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(name: str) -> as_Service:
    return as_Service(name=name)


def _make_offer(
    dl: SqliteDataLayer,
    report: as_VulnerabilityReport,
    recipient_id: str,
    actor_id: str,
):
    """Create and persist an Offer + VultronOfferRecord in the DataLayer."""
    offer = rm_submit_report_activity(report, recipient_id, actor=actor_id)
    dl.create(offer)
    offer_record = VultronOfferRecord(
        offer_id=offer.id_,
        report_id=report.id_,
        offer_actor_id=actor_id,
        offer_to=[recipient_id],
    )
    dl.create(offer_record)
    return offer


def _build_case(
    dl: SqliteDataLayer,
    vendor_id: str,
    finder_id: str,
    case_actor_id: str,
    report_id: str,
) -> as_VulnerabilityCase:
    """Build a VulnerabilityCase with full participant setup and linked report."""
    case = as_VulnerabilityCase(name="Chain Integration Case")
    case.vulnerability_reports.append(report_id)

    vendor_p = as_CaseParticipant(
        attributed_to=vendor_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
    )
    vendor_p.participant_statuses.append(
        WireParticipantStatus(context=case.id_, rm_state=RM.RECEIVED)
    )

    finder_p = FinderParticipant(
        attributed_to=finder_id,
        context=case.id_,
    )
    case_manager_p = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )

    case.actor_participant_index[vendor_id] = vendor_p.id_
    case.actor_participant_index[finder_id] = finder_p.id_
    case.actor_participant_index[case_actor_id] = case_manager_p.id_
    case.case_participants[:] = [
        vendor_p.id_,
        finder_p.id_,
        case_manager_p.id_,
    ]

    dl.create(case)
    dl.create(vendor_p)
    dl.create(finder_p)
    dl.create(case_manager_p)
    return case


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def chain_context():
    """Vendor DataLayer pre-seeded with report, offer, and case.

    Mirrors how the vendor's DataLayer looks after receiving a SubmitReport
    from the finder and creating the local case at RM.RECEIVED.
    """
    finder = _make_actor("Finder Co")
    vendor = _make_actor("Vendor Co")
    case_actor = _make_actor("Case Actor")

    reset_datalayer(vendor.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=vendor.id_)
    dl.clear_all()
    for actor in (finder, vendor, case_actor):
        dl.create(actor)

    report = as_VulnerabilityReport(
        name="Chain Test Vuln",
        content="Heap overflow in login handler",
        attributed_to=finder.id_,
    )
    dl.create(report)

    offer = _make_offer(dl, report, vendor.id_, actor_id=finder.id_)

    case = _build_case(dl, vendor.id_, finder.id_, case_actor.id_, report.id_)

    yield vendor, finder, case_actor, dl, report, offer, case

    dl.clear_all()
    dl.close()
    for actor in (finder, vendor, case_actor):
        reset_datalayer(actor.id_)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidateEngageChain:
    """ValidateReport → EngageCase produces RM.ACCEPTED from RM.RECEIVED."""

    def test_validate_report_advances_rm_to_valid(self, chain_context):
        """ValidateReport transitions the vendor's RM from RECEIVED to VALID."""
        vendor, _, _, dl, _, offer, case = chain_context

        SvcValidateReportUseCase(
            dl,
            ValidateReportTriggerRequest(
                actor_id=vendor.id_,
                offer_id=offer.id_,
            ),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        vendor_p_id = case.actor_participant_index[vendor.id_]
        updated = cast(CaseParticipant, dl.read(vendor_p_id))
        assert updated is not None
        assert updated.participant_statuses
        assert updated.participant_statuses[-1].rm.state == RM.VALID

    def test_engage_case_advances_rm_to_accepted(self, chain_context):
        """After Validate, EngageCase transitions RM to ACCEPTED."""
        vendor, _, _, dl, _, offer, case = chain_context

        SvcValidateReportUseCase(
            dl,
            ValidateReportTriggerRequest(
                actor_id=vendor.id_, offer_id=offer.id_
            ),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        SvcEngageCaseUseCase(
            dl,
            EngageCaseTriggerRequest(actor_id=vendor.id_, case_id=case.id_),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        vendor_p_id = case.actor_participant_index[vendor.id_]
        updated = cast(CaseParticipant, dl.read(vendor_p_id))
        assert updated is not None
        assert updated.participant_statuses
        assert updated.participant_statuses[-1].rm.state == RM.ACCEPTED

    def test_full_chain_rm_sequence(self, chain_context):
        """RM state history includes RECEIVED → VALID → ACCEPTED in order."""
        vendor, _, _, dl, _, offer, case = chain_context

        SvcValidateReportUseCase(
            dl,
            ValidateReportTriggerRequest(
                actor_id=vendor.id_, offer_id=offer.id_
            ),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        SvcEngageCaseUseCase(
            dl,
            EngageCaseTriggerRequest(actor_id=vendor.id_, case_id=case.id_),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        vendor_p_id = case.actor_participant_index[vendor.id_]
        participant = cast(CaseParticipant, dl.read(vendor_p_id))
        assert participant is not None
        rm_history = [s.rm.state for s in participant.participant_statuses]

        assert RM.RECEIVED in rm_history, "RM.RECEIVED must appear in history"
        assert RM.VALID in rm_history, "RM.VALID must appear in history"
        assert RM.ACCEPTED in rm_history, "RM.ACCEPTED must appear in history"

        # ACCEPTED must come after VALID
        valid_idx = next(i for i, s in enumerate(rm_history) if s == RM.VALID)
        accepted_idx = next(
            i for i, s in enumerate(rm_history) if s == RM.ACCEPTED
        )
        assert (
            accepted_idx > valid_idx
        ), "RM.ACCEPTED must come after RM.VALID in the participant status history"

    def test_validate_report_queues_activity_addressed_to_case_actor(
        self, chain_context
    ):
        """ValidateReport queues an activity addressed to the Case Actor (PCR-08-001)."""
        vendor, _, case_actor, dl, _, offer, _ = chain_context

        before = set(dl.outbox_list())
        SvcValidateReportUseCase(
            dl,
            ValidateReportTriggerRequest(
                actor_id=vendor.id_, offer_id=offer.id_
            ),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()
        after = set(dl.outbox_list())
        new_ids = after - before
        assert (
            new_ids
        ), "ValidateReport must queue at least one outbox activity"

        activity_id = next(iter(new_ids))
        activity = dl.read(activity_id)
        assert activity is not None
        to = getattr(activity, "to", None)
        to_ids = (
            [
                (
                    item
                    if isinstance(item, str)
                    else getattr(item, "id_", str(item))
                )
                for item in to
            ]
            if isinstance(to, list)
            else ([to] if isinstance(to, str) else [])
        )
        assert (
            case_actor.id_ in to_ids
        ), f"PCR-08-001: ValidateReport activity must address CaseActor; to={to_ids!r}"
