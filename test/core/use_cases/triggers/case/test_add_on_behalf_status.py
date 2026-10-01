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
- PRM-06-003: Case Manager asserts v→V for an existing vendor participant;
  only VF changes.
- PRM-06-004: d→D for an existing deployer succeeds only at an RM the
  RM↔D entailment permits.
- PRM-06-006: a non-participant target is refused and nothing is created.
- Blocked when asserting actor lacks CM/CO role.
- AC-5 (request layer): CS_vf.VF is rejected at the request boundary.
- AC-4: Vendor-implies-V invariant blocks a joined vendor from asserting vf.
"""

from typing import NamedTuple

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    RmDimension,
    VfDimension,
)
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers.case import (
    AddOnBehalfStatusTriggerRequest,
    AddParticipantStatusTriggerRequest,
    SvcAddOnBehalfStatusUseCase,
    SvcAddParticipantStatusUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
    as_ParticipantStatus,
)
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


def _add_participant(
    dl: SqliteDataLayer,
    case: as_VulnerabilityCase,
    actor_id: str,
    roles: list[CVDRole],
    rm: RM,
    vf: CS_vf | None = None,
) -> as_CaseParticipant:
    """Attach an existing participant at ``rm`` (and ``vf``, for a vendor)."""
    participant = as_CaseParticipant(
        attributed_to=actor_id,
        context=case.id_,
        case_roles=roles,
        participant_statuses=[
            as_ParticipantStatus(
                attributed_to=actor_id,
                context=case.id_,
                rm=RmDimension(state=rm),
                vf=VfDimension(state=vf) if vf is not None else None,
            )
        ],
    )
    case.actor_participant_index[actor_id] = participant.id_
    case.case_participants.append(participant.id_)
    dl.create(participant)
    dl.save(case)
    return participant


class _StoreState(NamedTuple):
    """Roster, stored-object counts and outbox — what a refusal must not touch."""

    roster: dict[str, str]
    participants: list[object]
    counts: dict[str, int]
    outbox: set[str]


def _store_state(dl: SqliteDataLayer, case_id: str) -> _StoreState:
    case = dl.read_case(case_id)
    assert case is not None
    return _StoreState(
        roster=dict(case.actor_participant_index),
        participants=list(case.case_participants),
        counts=dl.count_all(),
        outbox=set(dl.outbox_list()),
    )


def _run(dl: SqliteDataLayer, request: AddOnBehalfStatusTriggerRequest):
    return SvcAddOnBehalfStatusUseCase(
        dl, request, trigger_activity=TriggerActivityAdapter(dl)
    ).execute()


def _last_status(dl: SqliteDataLayer, case_id: str, actor_id: str):
    case = dl.read_case(case_id)
    assert case is not None
    participant = dl.read(case.actor_participant_index[actor_id])
    assert isinstance(participant, CaseParticipant)
    return participant, participant.participant_statuses[-1]


class TestAddOnBehalfStatusVtoV:
    """PRM-06-003: Case Manager asserts v→V for an existing vendor participant."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.cm_actor, self.dl = _make_actor_dl("CaseManager")
        self.vendor_actor = _make_actor("Vendor Co")
        self.case = _make_base_case(self.dl, self.cm_actor.id_)
        yield
        self.dl.clear_all()
        reset_datalayer(self.cm_actor.id_)

    def _request(self) -> AddOnBehalfStatusTriggerRequest:
        return AddOnBehalfStatusTriggerRequest(
            actor_id=self.cm_actor.id_,
            case_id=self.case.id_,
            target_actor_id=self.vendor_actor.id_,
            vf_state=CS_vf.Vf,
        )

    @pytest.mark.spec("PRM-06-006")
    def test_refuses_non_participant_vendor_and_creates_nothing(self):
        """A status update is never a way into a case (PRM-06-006)."""
        before = _store_state(self.dl, self.case.id_)

        with pytest.raises(VultronValidationError) as excinfo:
            _run(self.dl, self._request())

        message = str(excinfo.value)
        assert self.vendor_actor.id_ in message
        assert "PRM-06-006" in message
        assert _store_state(self.dl, self.case.id_) == before

    @pytest.mark.spec("PRM-06-003")
    def test_changes_only_vf_of_an_inert_vendor_invitee(self):
        """v→V moves VF only; the invitee's RM stays at RECEIVED."""
        _add_participant(
            self.dl,
            self.case,
            self.vendor_actor.id_,
            [CVDRole.VENDOR],
            RM.RECEIVED,
            CS_vf.vf,
        )
        before = _store_state(self.dl, self.case.id_)

        result = _run(self.dl, self._request())

        participant, last = _last_status(
            self.dl, self.case.id_, self.vendor_actor.id_
        )
        assert last.id_ == result.status_id
        assert last.vf is not None and last.vf.state == CS_vf.Vf
        assert last.rm is not None and last.rm.state == RM.RECEIVED
        assert last.d is None
        assert participant.roles == [CVDRole.VENDOR]
        after = _store_state(self.dl, self.case.id_)
        assert (after.roster, after.participants) == (
            before.roster,
            before.participants,
        )

    def test_queues_outbox_activity_addressed_to_case_manager(self):
        _add_participant(
            self.dl,
            self.case,
            self.vendor_actor.id_,
            [CVDRole.VENDOR],
            RM.RECEIVED,
            CS_vf.vf,
        )
        before = set(self.dl.outbox_list())
        _run(self.dl, self._request())

        after = set(self.dl.outbox_list())
        new_ids = after - before
        assert new_ids, "on-behalf assertion must queue an outbox activity"
        activity_id = next(iter(new_ids))
        activity = self.dl.read(activity_id)
        assert activity is not None
        to_ids = _to_ids(activity)
        assert self.cm_actor.id_ in to_ids, (
            f"PCR-08-001: activity must address the Case Manager; to={to_ids!r}"
        )

    @pytest.mark.spec("PRM-06-003")
    def test_refuses_target_without_vendor_role(self):
        """v→V is asserted on behalf of a Vendor-role participant only."""
        _add_participant(
            self.dl,
            self.case,
            self.vendor_actor.id_,
            [CVDRole.DEPLOYER],
            RM.ACCEPTED,
        )
        before = _store_state(self.dl, self.case.id_)

        with pytest.raises(VultronValidationError) as excinfo:
            _run(self.dl, self._request())

        assert self.vendor_actor.id_ in str(excinfo.value)
        assert "does not hold vendor" in str(excinfo.value)
        assert _store_state(self.dl, self.case.id_) == before

    def test_refuses_target_whose_indexed_record_is_missing(self):
        """An index entry with no stored record is refused, not repaired."""
        self.case.actor_participant_index[self.vendor_actor.id_] = (
            "https://example.org/participants/missing"
        )
        self.dl.save(self.case)
        before = _store_state(self.dl, self.case.id_)

        with pytest.raises(VultronValidationError) as excinfo:
            _run(self.dl, self._request())

        message = str(excinfo.value)
        assert self.vendor_actor.id_ in message
        assert "participant record" in message
        assert "could not be read" in message
        assert "is not a participant" not in message
        assert _store_state(self.dl, self.case.id_) == before

    def test_blocked_when_asserting_actor_not_cm_or_co(self):
        """Non-CM/CO actor cannot make an on-behalf assertion (PRM-06-003)."""
        _add_participant(
            self.dl,
            self.case,
            self.vendor_actor.id_,
            [CVDRole.VENDOR],
            RM.RECEIVED,
            CS_vf.vf,
        )
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
        before = _store_state(self.dl, self.case.id_)

        request = AddOnBehalfStatusTriggerRequest(
            actor_id=coordinator_actor.id_,
            case_id=self.case.id_,
            target_actor_id=self.vendor_actor.id_,
            vf_state=CS_vf.Vf,
        )
        with pytest.raises(VultronValidationError):
            _run(self.dl, request)
        assert _store_state(self.dl, self.case.id_) == before


class TestAddOnBehalfStatusDtoD:
    """PRM-06-004: d→D on behalf of an existing deployer participant."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.cm_actor, self.dl = _make_actor_dl("CaseManager")
        self.vendor_actor = _make_actor("Vendor Co")
        self.deployer_actor = _make_actor("Deployer Inc")
        self.case = _make_base_case(self.dl, self.cm_actor.id_)
        # The CSB-15-004 causal precondition: some vendor has a fix.
        _add_participant(
            self.dl,
            self.case,
            self.vendor_actor.id_,
            [CVDRole.VENDOR],
            RM.ACCEPTED,
            CS_vf.VF,
        )
        yield
        self.dl.clear_all()
        reset_datalayer(self.cm_actor.id_)

    def _request(self) -> AddOnBehalfStatusTriggerRequest:
        return AddOnBehalfStatusTriggerRequest(
            actor_id=self.cm_actor.id_,
            case_id=self.case.id_,
            target_actor_id=self.deployer_actor.id_,
            d_state=CS_d.D,
        )

    @pytest.mark.spec("PRM-06-004")
    @pytest.mark.parametrize("rm", [RM.ACCEPTED, RM.DEFERRED, RM.CLOSED])
    def test_succeeds_for_deployer_at_rm_consistent_with_deployment(
        self, rm: RM
    ):
        _add_participant(
            self.dl, self.case, self.deployer_actor.id_, [CVDRole.DEPLOYER], rm
        )

        result = _run(self.dl, self._request())

        _, last = _last_status(self.dl, self.case.id_, self.deployer_actor.id_)
        assert last.id_ == result.status_id
        assert last.d is not None and last.d.state == CS_d.D
        assert last.rm is not None and last.rm.state == rm

    @pytest.mark.spec("PRM-06-004")
    @pytest.mark.spec("BTND-10-002")
    @pytest.mark.parametrize("rm", [RM.RECEIVED, RM.INVALID, RM.VALID])
    def test_refused_by_entailment_at_any_other_rm(self, rm: RM):
        """D entails RM ∈ {ACCEPTED, DEFERRED, CLOSED}; nothing is written."""
        _add_participant(
            self.dl, self.case, self.deployer_actor.id_, [CVDRole.DEPLOYER], rm
        )
        before = _store_state(self.dl, self.case.id_)

        with pytest.raises(VultronValidationError) as excinfo:
            _run(self.dl, self._request())

        assert excinfo.value.violations, "the entailment names its rule"
        assert _store_state(self.dl, self.case.id_) == before
        _, last = _last_status(self.dl, self.case.id_, self.deployer_actor.id_)
        assert last.rm is not None and last.rm.state == rm
        assert last.d is None or last.d.state == CS_d.d

    @pytest.mark.spec("PRM-06-006")
    def test_refuses_non_participant_deployer_and_creates_nothing(self):
        before = _store_state(self.dl, self.case.id_)

        with pytest.raises(VultronValidationError) as excinfo:
            _run(self.dl, self._request())

        assert self.deployer_actor.id_ in str(excinfo.value)
        assert "PRM-06-006" in str(excinfo.value)
        assert _store_state(self.dl, self.case.id_) == before

    @pytest.mark.spec("PRM-06-004")
    def test_refuses_target_without_deployer_role(self):
        """d→D on behalf of the vendor (no DEPLOYER role) is refused."""
        before = _store_state(self.dl, self.case.id_)
        request = AddOnBehalfStatusTriggerRequest(
            actor_id=self.cm_actor.id_,
            case_id=self.case.id_,
            target_actor_id=self.vendor_actor.id_,
            d_state=CS_d.D,
        )

        with pytest.raises(VultronValidationError) as excinfo:
            _run(self.dl, request)

        assert self.vendor_actor.id_ in str(excinfo.value)
        assert "does not hold deployer" in str(excinfo.value)
        assert _store_state(self.dl, self.case.id_) == before


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

    def test_vf_state_none_accepted_when_d_state_provided(self):
        req = AddOnBehalfStatusTriggerRequest(
            actor_id="https://example.org/cm",
            case_id="https://example.org/case",
            target_actor_id="https://example.org/deployer",
            d_state=CS_d.D,
        )
        assert req.vf_state is None
        assert req.d_state == CS_d.D

    def test_vf_state_vf_lower_rung_raises(self):
        """PRM-06-003 permits v→V only; recording unawareness is refused."""
        with pytest.raises(ValueError, match="only v→V"):
            AddOnBehalfStatusTriggerRequest(
                actor_id="https://example.org/cm",
                case_id="https://example.org/case",
                target_actor_id="https://example.org/vendor",
                vf_state=CS_vf.vf,
            )

    def test_d_state_d_lower_rung_raises(self):
        """PRM-06-004 permits d→D only; recording non-deployment is refused."""
        with pytest.raises(ValueError, match="only d→D"):
            AddOnBehalfStatusTriggerRequest(
                actor_id="https://example.org/cm",
                case_id="https://example.org/case",
                target_actor_id="https://example.org/deployer",
                d_state=CS_d.d,
            )

    def test_all_none_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            AddOnBehalfStatusTriggerRequest(
                actor_id="https://example.org/cm",
                case_id="https://example.org/case",
                target_actor_id="https://example.org/vendor",
            )


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
                rm=RmDimension(state=RM.ACCEPTED),
                vf=VfDimension(state=CS_vf.Vf),
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
