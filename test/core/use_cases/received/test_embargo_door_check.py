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
"""Every received embargo use case refuses an unaddressed copy (HP-01-005).

The door check (``unaddressed_copy_refusal``, ADR-0118, #4132) runs before
any tree: a receiver that neither sent the activity nor is named in its
``to``/``cc`` refuses it with a reason naming itself and the recipients the
sender chose, and writes nothing to its store or its outbox.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases._helpers import unaddressed_copy_refusal
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    AddEmbargoEventToCaseReceivedUseCase,
    AnnounceEmbargoEventToCaseReceivedUseCase,
    CreateEmbargoEventReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)

from .conftest import make_embargo_case_with_actor

_CASE = "https://example.org/cases/door-check"
_MANAGER = "https://example.org/users/coord"
_SENDER = "https://example.org/users/vendor"
_OTHER = "https://example.org/users/vendor-a"
#: Holds a copy it was never addressed: not the sender, not in to/cc.
_BYSTANDER = "https://example.org/users/vendor-b"

_USE_CASES = [
    CreateEmbargoEventReceivedUseCase,
    AddEmbargoEventToCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    AnnounceEmbargoEventToCaseReceivedUseCase,
]


def _request(embargo: Any, *, to: list[str], cc: list[str]) -> MagicMock:
    """A well-formed request from ``_SENDER``, received by ``_BYSTANDER``.

    Every id a use case's shape checks read is filled in, so the only fault
    left is the addressing.
    """
    request = MagicMock()
    request.receiving_actor_id = _BYSTANDER
    request.actor_id = _SENDER
    request.activity_id = f"{_CASE}/activities/a1"
    request.activity.to = to
    request.activity.cc = cc
    request.case_id = _CASE
    request.context_id = _CASE
    request.embargo_id = embargo.id_
    request.object_id = embargo.id_
    request.embargo = embargo
    request.object_type = "EmbargoEvent"
    request.invite_id = f"{_CASE}/activities/invite"
    request.invitee_id = to[0] if len(to) == 1 else None
    request.to_recipients = to
    return request


def _snapshot(dl: SqliteDataLayer) -> tuple[dict[str, Any], list[str]]:
    """Every stored record, by type, and the outbox."""
    records = {t: dl.by_type(t) for t in dl.count_all()}
    return records, list(dl.outbox_list())


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("EMB-01-002")
@pytest.mark.parametrize(
    "use_case", _USE_CASES, ids=[uc.__name__ for uc in _USE_CASES]
)
def test_an_unaddressed_copy_is_refused_before_any_write(use_case):
    dl, _actor, _case, embargo = make_embargo_case_with_actor(
        _CASE,
        _SENDER,
        extra_participants=[_OTHER, _BYSTANDER],
        case_manager_actor_id=_MANAGER,
    )
    before = _snapshot(dl)

    result = use_case(
        dl, _request(embargo, to=[_MANAGER], cc=[_OTHER])
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    reason = result.reason or ""
    assert "neither the sender nor a recipient" in reason
    assert _BYSTANDER in reason
    assert f"to=['{_MANAGER}']" in reason
    assert f"cc=['{_OTHER}']" in reason
    assert _snapshot(dl) == before


class TestUnaddressedCopyRefusal:
    """The shared helper admits the sender and every to/cc recipient."""

    @staticmethod
    def _event(to: list[str], cc: list[str]) -> MagicMock:
        event = MagicMock()
        event.actor_id = _SENDER
        event.activity_id = f"{_CASE}/activities/a2"
        event.activity.to = to
        event.activity.cc = cc
        return event

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.parametrize(
        "receiver, to, cc",
        [
            (_SENDER, [], []),
            (_MANAGER, [_MANAGER], []),
            (_MANAGER, [_OTHER], [_MANAGER]),
            (_MANAGER, [f"{_MANAGER}/"], []),
        ],
        ids=["sender", "to", "cc", "trailing-slash"],
    )
    def test_admits_the_sender_and_each_recipient(self, receiver, to, cc):
        event = self._event(to, cc)
        assert unaddressed_copy_refusal(receiver, event, label="Test") is None

    @pytest.mark.spec("HP-01-005")
    def test_refuses_an_event_with_no_activity(self):
        event = self._event([], [])
        event.activity = None
        result = unaddressed_copy_refusal(_BYSTANDER, event, label="Test")
        assert result is not None
        assert result.disposition is HandlerDisposition.REFUSED
        assert "to=[], cc=[]" in (result.reason or "")

    @pytest.mark.spec("HP-01-005")
    def test_refusal_logs_a_warning(self, caplog):
        event = self._event([_MANAGER], [])
        with caplog.at_level("WARNING"):
            unaddressed_copy_refusal(_BYSTANDER, event, label="Test")
        assert any(
            r.levelname == "WARNING" and _BYSTANDER in r.getMessage()
            for r in caplog.records
        )
