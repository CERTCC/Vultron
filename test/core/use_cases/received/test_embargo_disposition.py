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

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    AddEmbargoEventToCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_embargo_to_case_activity,
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
    def test_add_missing_ids(self, embargo_id, case_id):
        request = _request(embargo_id=embargo_id, case_id=case_id)
        result = AddEmbargoEventToCaseReceivedUseCase(
            _make_dl(), request
        ).execute()
        _assert_refused(result, "missing")

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.parametrize(
        "embargo_id, case_id",
        [(None, "https://example.org/cases/c1"), ("e1", None)],
    )
    def test_remove_missing_ids(self, embargo_id, case_id):
        request = _request(embargo_id=embargo_id, case_id=case_id)
        result = RemoveEmbargoEventFromCaseReceivedUseCase(
            _make_dl(), request
        ).execute()
        _assert_refused(result, "missing")

    @pytest.mark.spec("HP-01-003")
    def test_invite_missing_activity_id(self):
        request = _request(
            activity_id=None, context_id="https://example.org/cases/c1"
        )
        result = InviteToEmbargoOnCaseReceivedUseCase(
            _make_dl(), request
        ).execute()
        _assert_refused(result, "missing")

    @pytest.mark.spec("HP-01-003")
    def test_accept_missing_embargo_id(self):
        request = _request(embargo_id=None)
        result = AcceptInviteToEmbargoOnCaseReceivedUseCase(
            _make_dl(), request
        ).execute()
        _assert_refused(result, "missing")

    @pytest.mark.spec("HP-01-003")
    def test_reject_missing_case_id(self):
        request = _request(case_id=None, invite_id="i1", actor_id=_VENDOR)
        result = RejectInviteToEmbargoOnCaseReceivedUseCase(
            _make_dl(), request
        ).execute()
        _assert_refused(result, "case")


class TestEmbargoMessagesForUnknownCaseAreRefused:
    @pytest.mark.spec("HP-01-003")
    def test_add_to_unknown_case(self, make_payload):
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/nope/embargo_events/e1",
            context="https://example.org/cases/nope",
        )
        activity = add_embargo_to_case_activity(
            embargo,
            target=as_VulnerabilityCase(id_="https://example.org/cases/nope"),
            actor=_VENDOR,
        )
        event = make_payload(activity, receiving_actor_id=_COORD)

        result = AddEmbargoEventToCaseReceivedUseCase(
            _make_dl(), event
        ).execute()

        _assert_refused(result, "AddEmbargoToCaseBT")

    @pytest.mark.spec("HP-01-003")
    def test_accept_for_unknown_case(self):
        request = _request(
            embargo_id="https://example.org/cases/nope/embargo_events/e1",
            case_id="https://example.org/cases/nope",
            invite_id="i1",
        )
        result = AcceptInviteToEmbargoOnCaseReceivedUseCase(
            _make_dl(), request
        ).execute()
        _assert_refused(result, "unknown case")


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
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_tdf",
            name="Teardown Failure",
            attributed_to=_COORD,
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_tdf/embargo_events/e1",
            context=case.id_,
        )
        case.active_embargo = embargo.id_
        case.append_case_status(em_state=EM.ACTIVE)
        dl.create(case)
        dl.create(embargo)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=as_VulnerabilityCase(id_=case.id_),
            actor=_VENDOR,
        )
        event = make_payload(activity, receiving_actor_id=_COORD)

        result = RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        _assert_refused(result, "could not clear active embargo")
