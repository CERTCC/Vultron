#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Tests for the Case Owner's removal and reinstatement use cases."""

from typing import cast

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
)
from test.support.act_runner import run_in_act
from test.support.objects import authored_at, make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.case_participant import (
    ReinstateParticipantInCaseReceivedUseCase,
    RemoveParticipantFromCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    reinstate_participant_activity,
    remove_participant_activity,
)


class TestCaseParticipantUseCases:
    """Tests for the remove and reinstate participant use cases."""

    @pytest.mark.spec("CM-31-001")
    def test_remove_case_participant_from_case(self, make_payload):
        """The record stays, the fact is set (ADR-0116)."""
        dl, case_id, participant = _removal_store()
        event = make_payload(_owner_removes(_COORDINATOR, case_id), at=dl)

        result = _remove(dl, event)

        assert result.disposition == HandlerDisposition.APPLIED
        case = cast(VulnerabilityCase, dl.read(case_id))
        assert participant.id_ in [
            getattr(p, "id_", p) for p in case.case_participants
        ]
        record = cast(CaseParticipant, dl.read(participant.id_))
        assert record.removal_activity == event.activity_id

    @pytest.mark.spec("CM-31-004")
    def test_removal_naming_an_actor_not_on_the_case_is_refused(
        self, make_payload
    ):
        """A removal naming no participant of the case is refused, not skipped.

        The tree still ran, so intake archived the delivery (CLP-10-017).
        """
        dl, case_id, _ = _removal_store()
        event = make_payload(_owner_removes(_STRANGER, case_id), at=dl)

        result = _remove(dl, event)

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "is not a participant" in result.reason
        assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))

    @pytest.mark.spec("CM-31-036")
    def test_reinstatement_does_not_seat_an_actor_off_the_roster(
        self, make_payload
    ):
        """A reinstatement only reinstates (ADR-0116).

        An actor with no record on the case names no participant, so the Case
        Owner's ``Add(<Actor>)`` is refused and the roster is unchanged;
        joining is accepting a stub Invite (ADR-0114).
        """
        dl, case_id, _ = _removal_store()
        before = cast(VulnerabilityCase, dl.read(case_id)).case_participants
        event = make_payload(_owner_reinstates(_STRANGER, case_id), at=dl)

        result = _move(ReinstateParticipantInCaseReceivedUseCase, dl, event)

        assert result.disposition == HandlerDisposition.REFUSED
        case = cast(VulnerabilityCase, dl.read(case_id))
        assert case.case_participants == before
        assert _STRANGER not in case.actor_participant_index
        # A refused delivery is still recorded by intake, for the outcome
        # stage to stub (CLP-10-017, CLP-10-018).
        assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))

    @pytest.mark.spec("HP-01-003")
    def test_remove_participant_from_unknown_case_is_refused(
        self, make_payload
    ):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
        event = make_payload(
            _owner_removes(
                _COORDINATOR, "https://example.org/cases/no-such-case"
            ),
            at=dl,
        )

        result = run_in_act(
            RemoveParticipantFromCaseReceivedUseCase(dl, event)
        )

        assert result.disposition == HandlerDisposition.REFUSED
        # The path stage, a door, refused the unknown case before intake.
        assert (
            dl.read(ReceivedActivityRecord.build_id(event.activity_id)) is None
        )

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.parametrize(
        "use_case, build",
        [
            (
                ReinstateParticipantInCaseReceivedUseCase,
                reinstate_participant_activity,
            ),
            (
                RemoveParticipantFromCaseReceivedUseCase,
                remove_participant_activity,
            ),
        ],
    )
    def test_move_naming_no_actor_is_refused(
        self, use_case, build, make_payload
    ):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
        event = make_payload(
            build(
                _COORDINATOR,
                "https://example.org/cases/c",
                actor=_OWNER,
                to=[_MANAGER],
                at=authored_at(),
            ),
            at=dl,
        ).model_copy(update={"object_": None})
        assert event.participant_actor_id is None

        result = run_in_act(use_case(dl, event))

        assert result.disposition == HandlerDisposition.REFUSED
        assert "missing the actor it names" in (result.reason or "")

    @pytest.mark.spec("CM-19-002")
    def test_remove_case_participant_keeps_index(self, make_payload):
        """The index entry stays: removal withdraws entitlement only."""
        dl, case_id, participant = _removal_store()
        event = make_payload(_owner_removes(_COORDINATOR, case_id), at=dl)

        _remove(dl, event)

        case = cast(VulnerabilityCase, dl.read(case_id))
        assert case.actor_participant_index[_COORDINATOR] == participant.id_


_MANAGER = "https://test.example/api/v2/actors/test-actor"
_OWNER = "https://example.org/users/owner"
_COORDINATOR = "https://example.org/users/coordinator"
_STRANGER = "https://example.org/users/stranger"


def _removal_store() -> tuple[SqliteDataLayer, str, CaseParticipant]:
    """A CASE_MANAGER store: the manager, the Case Owner and a coordinator."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
    case = make(
        VulnerabilityCase,
        id_="https://example.org/cases/caseRM1",
        name="TEST-REMOVE",
        attributed_to=_OWNER,
    )
    seed_case_manager_participant(dl, case, _MANAGER)
    seed_case_owner_participant(dl, case, _OWNER)
    participant = make(
        CaseParticipant,
        id_=f"{case.id_}/participants/coord",
        attributed_to=_COORDINATOR,
        context=case.id_,
    )
    dl.create(participant)
    case.add_participant(participant)
    dl.create(case)
    return dl, case.id_, participant


def _owner_removes(actor_id: str, case_id: str):
    return remove_participant_activity(
        actor_id, case_id, actor=_OWNER, to=[_MANAGER], at=authored_at()
    )


def _owner_reinstates(actor_id: str, case_id: str):
    return reinstate_participant_activity(
        actor_id, case_id, actor=_OWNER, to=[_MANAGER], at=authored_at()
    )


def _remove(dl: SqliteDataLayer, event):
    return _move(RemoveParticipantFromCaseReceivedUseCase, dl, event)


def _move(use_case, dl: SqliteDataLayer, event):
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.adapters.driven.wire_render import As2WireRenderAdapter

    return run_in_act(
        use_case(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        )
    )
