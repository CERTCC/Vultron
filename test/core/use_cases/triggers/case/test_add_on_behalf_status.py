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

"""Tests for SvcAddOnBehalfStatusUseCase.

Covers:
- AC-1: Case Manager asserts v→V for a notified-not-joined vendor.
- Blocked when asserting actor lacks CM/CO role.
- AC-5 (request layer): CS_vf.VF is rejected at the request boundary.
- AC-4: Vendor-implies-V invariant blocks a joined vendor from asserting vf.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.cs import CS_vf
from vultron.core.use_cases.triggers.case import (
    AddOnBehalfStatusTriggerRequest,
    AddParticipantStatusTriggerRequest,
    SvcAddOnBehalfStatusUseCase,
    SvcAddParticipantStatusUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _make_actor(name: str) -> as_Service:
    return as_Service(name=name, url=f"https://example.org/{name.lower()}")


def _make_actor_dl(name: str) -> tuple[as_Service, SqliteDataLayer]:
    actor = _make_actor(name)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _to_ids(activity) -> list[str]:
    to = getattr(activity, "to", None)
    if isinstance(to, list):
        return [
            item if isinstance(item, str) else getattr(item, "id_", str(item))
            for item in to
        ]
    if isinstance(to, str):
        return [to]
    return []


def _make_base_case(
    dl: SqliteDataLayer,
    case_manager_actor_id: str,
) -> as_VulnerabilityCase:
    """Return a case with one Case Manager participant; no vendor yet."""
    case = as_VulnerabilityCase(name="Test Case")
    cm_participant = as_CaseParticipant(
        attributed_to=case_manager_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[case_manager_actor_id] = cm_participant.id_
    case.case_participants.append(cm_participant.id_)
    dl.create(case)
    dl.create(cm_participant)
    return case


class TestAddOnBehalfStatusVtoV:
    """AC-1: Case Manager asserts v→V for a notified-but-not-joined vendor."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.cm_actor, self.dl = _make_actor_dl("CaseManager")
        self.vendor_actor = _make_actor("Vendor Co")
        self.case = _make_base_case(self.dl, self.cm_actor.id_)
        yield
        self.dl.clear_all()
        reset_datalayer(self.cm_actor.id_)

    def test_creates_participant_and_status_for_new_vendor(self):
        request = AddOnBehalfStatusTriggerRequest(
            actor_id=self.cm_actor.id_,
            case_id=self.case.id_,
            target_actor_id=self.vendor_actor.id_,
            vf_state=CS_vf.Vf,
        )
        result = SvcAddOnBehalfStatusUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        assert result.get("status_id") is not None

        # Vendor now has a CaseParticipant in the case
        updated_case = self.dl.read_case(self.case.id_)
        assert updated_case is not None
        assert self.vendor_actor.id_ in updated_case.actor_participant_index

        # Vendor's participant has a status with VF=Vf
        participant_id = updated_case.actor_participant_index[
            self.vendor_actor.id_
        ]
        participant = self.dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        assert participant.participant_statuses
        last_status = participant.participant_statuses[-1]
        assert last_status.vf is not None
        assert last_status.vf.state == CS_vf.Vf

    def test_queues_outbox_activity_addressed_to_case_manager(self):
        request = AddOnBehalfStatusTriggerRequest(
            actor_id=self.cm_actor.id_,
            case_id=self.case.id_,
            target_actor_id=self.vendor_actor.id_,
            vf_state=CS_vf.Vf,
        )
        before = set(self.dl.outbox_list())
        SvcAddOnBehalfStatusUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        after = set(self.dl.outbox_list())
        new_ids = after - before
        assert new_ids, "on-behalf assertion must queue an outbox activity"
        activity_id = next(iter(new_ids))
        activity = self.dl.read(activity_id)
        assert activity is not None
        to_ids = _to_ids(activity)
        assert (
            self.cm_actor.id_ in to_ids
        ), f"PCR-08-001: activity must address the Case Manager; to={to_ids!r}"

    def test_blocked_when_asserting_actor_not_cm_or_co(self):
        """Non-CM/CO actor cannot make an on-behalf assertion (PRM-06-003)."""
        coordinator_actor = _make_actor("Coordinator")
        # Register coordinator in the same DL so resolve_actor succeeds
        self.dl.create(coordinator_actor)
        coord_participant = as_CaseParticipant(
            attributed_to=coordinator_actor.id_,
            context=self.case.id_,
            case_roles=[CVDRole.COORDINATOR],
        )
        self.case.actor_participant_index[coordinator_actor.id_] = (
            coord_participant.id_
        )
        self.case.case_participants.append(coord_participant.id_)
        self.dl.save(self.case)
        self.dl.create(coord_participant)

        request = AddOnBehalfStatusTriggerRequest(
            actor_id=coordinator_actor.id_,
            case_id=self.case.id_,
            target_actor_id=self.vendor_actor.id_,
            vf_state=CS_vf.Vf,
        )
        with pytest.raises(VultronValidationError):
            SvcAddOnBehalfStatusUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()


class TestAddOnBehalfRequestValidation:
    """AC-3 / PRM-06-005: CS_vf.VF (f→F) rejected at request boundary."""

    def test_vf_state_VF_raises_at_request_construction(self):
        with pytest.raises(ValueError, match="f→F"):
            AddOnBehalfStatusTriggerRequest(
                actor_id="https://example.org/cm",
                case_id="https://example.org/case",
                target_actor_id="https://example.org/vendor",
                vf_state=CS_vf.VF,
            )

    def test_vf_state_Vf_accepted(self):
        req = AddOnBehalfStatusTriggerRequest(
            actor_id="https://example.org/cm",
            case_id="https://example.org/case",
            target_actor_id="https://example.org/vendor",
            vf_state=CS_vf.Vf,
        )
        assert req.vf_state == CS_vf.Vf

    def test_vf_state_none_accepted(self):
        req = AddOnBehalfStatusTriggerRequest(
            actor_id="https://example.org/cm",
            case_id="https://example.org/case",
            target_actor_id="https://example.org/vendor",
        )
        assert req.vf_state is None


class TestVendorImpliesVInvariant:
    """AC-4: A joined vendor cannot self-report CS_vf.vf (PRM-06-002)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor_actor, self.dl = _make_actor_dl("Vendor Co")
        self.cm_actor = _make_actor("Case Manager")
        self.case = _make_base_case(self.dl, self.cm_actor.id_)

        # Add the vendor as a joined participant with VENDOR role at CS_vf.Vf
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant as WireCaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.case_status import (
            as_ParticipantStatus as WireParticipantStatus,
        )

        vendor_participant = WireCaseParticipant(
            attributed_to=self.vendor_actor.id_,
            context=self.case.id_,
            case_roles=[CVDRole.VENDOR],
        )
        vendor_participant.participant_statuses.append(
            WireParticipantStatus(
                context=self.case.id_,
                rm_state="ACCEPTED",
                vf_state="Vf",
            )
        )
        self.case.actor_participant_index[self.vendor_actor.id_] = (
            vendor_participant.id_
        )
        self.case.case_participants.append(vendor_participant.id_)
        self.dl.save(self.case)
        self.dl.create(vendor_participant)
        yield
        self.dl.clear_all()
        reset_datalayer(self.vendor_actor.id_)

    def test_vendor_cannot_self_report_vf_unaware(self):
        """A joined vendor cannot assert CS_vf.vf (vendor-unaware) via self-report."""
        request = AddParticipantStatusTriggerRequest(
            actor_id=self.vendor_actor.id_,
            case_id=self.case.id_,
            vf_state=CS_vf.vf,
        )
        with pytest.raises(VultronValidationError):
            SvcAddParticipantStatusUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()
