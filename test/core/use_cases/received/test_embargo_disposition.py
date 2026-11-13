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
"""Embargo handlers report a refusal instead of claiming success (#2255).

A malformed message, a message about a case this replica does not hold, and a
tree that fails part-way are all ``REFUSED`` with a reason (HP-01-003), so the
inbox outcome says ``rejected`` rather than ``processed``.
"""

from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
)
from test.support.act_runner import run_in_act
from test.support.case_owner import CASE_OWNER_ID
from test.support.embargo_register import activate
from test.support.future_dates import days_from_now
from test.support.objects import authored_at, make
from test.support.owner_decision import (
    seeded_activation,
    seeded_proposal_rejection,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityIncompleteNode,
)
from vultron.core.behaviors.case.received_run import find_node
from vultron.core.behaviors.embargo.answer_trees import (
    accept_invite_to_embargo_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    ActivateEmbargoOnCaseReceivedUseCase,
    RejectEmbargoProposalOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.errors import VultronValidationError
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_COORD = "https://example.org/users/coord"
_VENDOR = "https://example.org/users/vendor"


def _make_dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_COORD)


def _request(**attrs) -> MagicMock:
    request = MagicMock()
    request.receiving_actor_id = _COORD
    request.activity_id = "https://example.org/activities/a1"
    # Addressed to the receiver, so the door check (HP-01-005) admits it
    # and each test reaches the shape fault it pins.
    request.activity.to = [_COORD]
    request.activity.cc = []
    for name, value in attrs.items():
        setattr(request, name, value)
    return request


def _assert_refused(result, fragment: str) -> None:
    assert result.disposition is HandlerDisposition.REFUSED
    assert fragment in (result.reason or "")


class TestMalformedEmbargoMessagesAreRefused:
    @pytest.mark.spec("HP-01-003")
    @pytest.mark.parametrize(
        "embargo_id, case_id",
        [(None, "https://example.org/cases/c1"), ("e1", None)],
    )
    @pytest.mark.parametrize(
        "use_case",
        [
            ActivateEmbargoOnCaseReceivedUseCase,
            RejectEmbargoProposalOnCaseReceivedUseCase,
        ],
    )
    def test_owner_decision_missing_ids(self, embargo_id, case_id, use_case):
        request = _request(embargo_id=embargo_id, case_id=case_id)
        result = run_in_act(use_case(_make_dl(), request))
        _assert_refused(result, "missing")

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.parametrize(
        "embargo_id, case_id",
        [(None, "https://example.org/cases/c1"), ("e1", None)],
    )
    def test_remove_missing_ids(self, embargo_id, case_id):
        request = _request(embargo_id=embargo_id, case_id=case_id)
        result = run_in_act(
            RemoveEmbargoEventFromCaseReceivedUseCase(_make_dl(), request)
        )
        _assert_refused(result, "missing")

    @pytest.mark.spec("HP-01-003")
    def test_accept_missing_embargo_id(self):
        request = _request(embargo_id=None)
        result = run_in_act(
            AcceptInviteToEmbargoOnCaseReceivedUseCase(_make_dl(), request)
        )
        _assert_refused(result, "missing")

    @pytest.mark.spec("HP-01-003")
    def test_reject_missing_embargo_id(self):
        """A Reject that names no embargo is malformed, like an Accept that does.

        Which terms are refused decides the consent effect (MSM-07-004), so
        the handler refuses rather than guessing.
        """
        request = _request(
            case_id="https://example.org/cases/c1",
            embargo_id=None,
            invite_id="i1",
            actor_id=_VENDOR,
        )
        result = run_in_act(
            RejectInviteToEmbargoOnCaseReceivedUseCase(_make_dl(), request)
        )
        _assert_refused(result, "embargo")

    @pytest.mark.spec("HP-01-003")
    def test_reject_missing_case_id(self):
        request = _request(case_id=None, invite_id="i1", actor_id=_VENDOR)
        result = run_in_act(
            RejectInviteToEmbargoOnCaseReceivedUseCase(_make_dl(), request)
        )
        _assert_refused(result, "case")


class TestEmbargoMessagesForUnknownCaseAreRefused:
    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("HP-01-039")
    @pytest.mark.spec("HP-01-040")
    @pytest.mark.parametrize(
        "factory, use_case",
        [
            (seeded_activation, ActivateEmbargoOnCaseReceivedUseCase),
            (
                seeded_proposal_rejection,
                RejectEmbargoProposalOnCaseReceivedUseCase,
            ),
        ],
    )
    def test_owner_decision_on_unknown_case(
        self, make_payload, factory, use_case
    ):
        """A case this store does not hold is the no-case path, and refused.

        The owner's decision is the CASE_MANAGER's to record, so its tree
        declares that path alone; a store holding no replica of the case the
        decision names resolves the no-case path and the stage refuses the
        delivery there, naming the case rather than the tree (HP-01-039,
        HP-01-040).
        """
        embargo = make(
            as_EmbargoEvent,
            id_="https://example.org/cases/nope/embargo_events/e1",
            context="https://example.org/cases/nope",
            end_time=days_from_now(45),
        )
        activity = factory(
            embargo,
            target=make(
                as_VulnerabilityCase,
                attributed_to=CASE_OWNER_ID,
                id_="https://example.org/cases/nope",
            ),
            actor=_VENDOR,
            to=[_COORD],
        )
        event = make_payload(activity, receiving_actor_id=_COORD)

        result = run_in_act(use_case(_make_dl(), event))

        _assert_refused(
            result, "holds no replica of case 'https://example.org/cases/nope'"
        )

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("HP-01-039")
    def test_accept_for_unknown_case(self, make_payload):
        """An Accept naming a case this store does not hold is refused at
        the path stage, on the no-case path, and nothing is recorded: the
        handler reads no store before its tree runs (HP-01-039)."""
        case_id = "https://example.org/cases/nope"
        embargo = make(
            as_EmbargoEvent,
            id_=f"{case_id}/embargo_events/e1",
            context=case_id,
            end_time=days_from_now(45),
        )
        invite = em_propose_embargo_activity(
            embargo,
            context=case_id,
            actor=_COORD,
            to=[_VENDOR],
            at=authored_at(),
        )
        accept = em_accept_embargo_activity(
            invite,
            context=case_id,
            actor=_VENDOR,
            to=[_COORD],
            at=authored_at(),
        )
        dl = _make_dl()
        event = make_payload(accept, receiving_actor_id=_COORD)

        result = run_in_act(
            AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event)
        )

        _assert_refused(result, f"holds no replica of case '{case_id}'")
        assert dl.list_objects("CaseLedgerEntry") == []
        assert dl.outbox_list() == []

    @pytest.mark.spec("HP-01-003")
    def test_accept_naming_no_case_is_refused_as_incomplete(self):
        """An Accept naming no case gets the incomplete-activity tree, whose
        guard refuses it after intake (CLP-10-018)."""
        tree = accept_invite_to_embargo_tree(
            case_id=None,
            embargo_id="https://example.org/embargo_events/e1",
            accepting_actor_id=_VENDOR,
            invite_id="https://example.org/activities/i1",
            sender_rule=AcceptInviteToEmbargoOnCaseReceivedUseCase.sender_entitlement,
        )
        assert find_node(tree, ActivityIncompleteNode) is not None

    @pytest.mark.spec("BT-17-009")
    @pytest.mark.spec("ARCH-15-001")
    def test_accept_with_no_resolvable_receiver_raises_before_any_read(
        self, anonymous_store
    ):
        """No receiver stamp and a store with no owner: a wiring fault.

        The receiver is resolved before the case is read, so an unknown case
        does not turn our fault into a refusal of the sender (#5774).
        """
        request = _request(
            embargo_id="https://example.org/cases/nope/embargo_events/e1",
            case_id="https://example.org/cases/nope",
            invite_id="i1",
            receiving_actor_id=None,
        )
        with pytest.raises(VultronValidationError):
            run_in_act(
                AcceptInviteToEmbargoOnCaseReceivedUseCase(
                    anonymous_store(_make_dl()), request
                )
            )


class TestFailedTeardownIsRefused:
    @pytest.mark.spec("HP-01-003")
    def test_remove_active_embargo_with_failing_step(
        self, make_payload, monkeypatch
    ):
        """A teardown step that fails is reported, not absorbed (#2255)."""
        from vultron.core.behaviors.embargo import nodes

        def _fail(self):
            self.feedback_message = "could not clear active embargo"
            return Status.FAILURE

        monkeypatch.setattr(nodes.ClearActiveEmbargoNode, "update", _fail)

        dl = _make_dl()
        case = make(
            VulnerabilityCase,
            id_="https://example.org/cases/case_tdf",
            name="Teardown Failure",
            attributed_to=_COORD,
        )
        embargo = make(
            as_EmbargoEvent,
            id_="https://example.org/cases/case_tdf/embargo_events/e1",
            context=case.id_,
            end_time=days_from_now(45),
        )
        activate(case, embargo.id_)
        seed_case_manager_participant(dl, case, _COORD)
        seed_case_owner_participant(dl, case, _VENDOR)
        dl.create(case)
        dl.create(embargo)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=make(
                as_VulnerabilityCase, attributed_to=CASE_OWNER_ID, id_=case.id_
            ),
            actor=_VENDOR,
            to=[_COORD],
            reason=TerminationReason.EARLY,
            at=authored_at(),
        )
        event = make_payload(activity, receiving_actor_id=_COORD, at=dl)

        result = run_in_act(
            RemoveEmbargoEventFromCaseReceivedUseCase(
                dl,
                event,
                sync_port=SyncActivityAdapter(dl),
                wire_render_port=As2WireRenderAdapter(),
            )
        )

        _assert_refused(result, "could not clear active embargo")
