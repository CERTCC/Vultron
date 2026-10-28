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

The door check is the tree's addressee guard
(``ActivityAddressedToReceiverNode``, ADR-0118, #4132), between the
post-close boundary and the sender guard (CLP-10-010): a receiver that
neither sent the activity nor is named in its ``to`` refuses it with a reason
naming itself and the recipients the sender chose.  Intake has archived the
copy (CLP-10-018); nothing else is written to its store or its outbox.
"""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    ActivateEmbargoOnCaseReceivedUseCase,
    AnnounceEmbargoEventToCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectEmbargoProposalOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
    WithdrawFromEmbargoOnCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    announce_embargo_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    reject_embargo_proposal_activity,
    remove_embargo_from_case_activity,
    withdraw_from_embargo_activity,
)

from .conftest import make_embargo_case_with_actor

_CASE = "https://example.org/cases/door-check"
_MANAGER = "https://example.org/users/coord"
_SENDER = "https://example.org/users/vendor"
_OTHER = "https://example.org/users/vendor-a"
#: Holds a copy it was never addressed: not the sender, not in to/cc.
_BYSTANDER = "https://example.org/users/vendor-b"

_ADDRESSING: dict[str, Any] = {
    "actor": _SENDER,
    "to": [_MANAGER],
    "cc": [_OTHER],
}


def _invite(embargo: Any) -> Any:
    return em_propose_embargo_activity(
        embargo,
        context=_CASE,
        id_=f"{_CASE}/activities/invite",
        **_ADDRESSING,
    )


#: Each use case and the activity it receives, from _SENDER to _MANAGER.
_ACTIVITIES: dict[type, Callable[[Any], Any]] = {
    ActivateEmbargoOnCaseReceivedUseCase: lambda e: activate_embargo_activity(
        e, target=_CASE, context=_CASE, **_ADDRESSING
    ),
    RejectEmbargoProposalOnCaseReceivedUseCase: (
        lambda e: reject_embargo_proposal_activity(
            e, target=_CASE, context=_CASE, **_ADDRESSING
        )
    ),
    RemoveEmbargoEventFromCaseReceivedUseCase: (
        lambda e: remove_embargo_from_case_activity(
            e,
            origin=_CASE,
            context=_CASE,
            reason=TerminationReason.EARLY,
            **_ADDRESSING,
        )
    ),
    WithdrawFromEmbargoOnCaseReceivedUseCase: (
        lambda e: withdraw_from_embargo_activity(
            e, context=_CASE, **_ADDRESSING
        )
    ),
    InviteToEmbargoOnCaseReceivedUseCase: _invite,
    AcceptInviteToEmbargoOnCaseReceivedUseCase: (
        lambda e: em_accept_embargo_activity(
            _invite(e), context=_CASE, **_ADDRESSING
        )
    ),
    RejectInviteToEmbargoOnCaseReceivedUseCase: (
        lambda e: em_reject_embargo_activity(
            _invite(e), context=_CASE, **_ADDRESSING
        )
    ),
    AnnounceEmbargoEventToCaseReceivedUseCase: (
        lambda e: announce_embargo_activity(e, context=_CASE, **_ADDRESSING)
    ),
}


def _snapshot(dl: SqliteDataLayer) -> tuple[dict[str, Any], list[str]]:
    """Every stored record but intake's archive, by type, and the outbox."""
    records = {
        t: dl.by_type(t)
        for t in dl.count_all()
        if t != ReceivedActivityRecord.__name__
    }
    return records, list(dl.outbox_list())


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("EMB-01-002")
@pytest.mark.spec("CLP-10-010")
@pytest.mark.parametrize(
    "use_case", list(_ACTIVITIES), ids=[uc.__name__ for uc in _ACTIVITIES]
)
def test_an_unaddressed_copy_is_refused_before_any_write(
    use_case, make_payload
):
    dl, _actor, _case, embargo = make_embargo_case_with_actor(
        _CASE,
        _SENDER,
        extra_participants=[_OTHER, _BYSTANDER],
        case_manager_actor_id=_MANAGER,
    )
    activity = _ACTIVITIES[use_case](embargo)
    before = _snapshot(dl)

    result = use_case(
        dl, make_payload(activity, receiving_actor_id=_BYSTANDER, at=dl)
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    reason = result.reason or ""
    assert "neither the sender nor a recipient" in reason
    assert _BYSTANDER in reason
    assert f"to=['{_MANAGER}']" in reason
    # cc has no handler semantics and core does not carry it (ADR-0109).
    assert "cc=" not in reason
    assert _snapshot(dl) == before


@pytest.mark.spec("EP-09-010")
@pytest.mark.spec("HP-01-006")
@pytest.mark.parametrize(
    "use_case",
    [
        AcceptInviteToEmbargoOnCaseReceivedUseCase,
        RejectInviteToEmbargoOnCaseReceivedUseCase,
    ],
    ids=["accept", "reject"],
)
def test_an_answer_naming_no_invite_is_refused_before_any_write(use_case):
    """The invitee is read from the recorded Invite, so none means no invitee.

    The refusal comes before any tree: the activity cannot name the Invite
    whose invitee the sender guard would check (EP-09-010).
    """
    dl, _actor, _case, embargo = make_embargo_case_with_actor(
        _CASE, _SENDER, case_manager_actor_id=_MANAGER
    )
    request = MagicMock()
    request.receiving_actor_id = _MANAGER
    request.actor_id = _SENDER
    request.case_id = _CASE
    request.embargo_id = embargo.id_
    request.invite_id = None
    before = _snapshot(dl)

    result = use_case(dl, request).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert "is missing its Invite id" in (result.reason or "")
    assert _snapshot(dl) == before
