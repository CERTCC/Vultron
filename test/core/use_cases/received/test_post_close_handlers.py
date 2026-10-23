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

"""Handlers that write or answer before their tree still honour CM-23-013.

The factory's post-close guard stops a received tree before its commit and
before any ER, late-Accept answer or ProcessingFault the tree would send.
After the CASE_MANAGER's own RM.CLOSED entry none of that may happen: it is
``REFUSED``, nothing is recorded and nothing is sent (CM-23-013, CM-23-017).
"""

from typing import Any

import pytest

from test.support.ledger import commit_case_manager_closure
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
)

from .conftest import make_embargo_case_with_actor

_CASE = "https://example.org/cases/post-close-handlers"
_MANAGER = "https://example.org/users/pc-coord"
_SENDER = "https://example.org/users/pc-vendor"


def _close(dl: SqliteDataLayer) -> None:
    commit_case_manager_closure(dl, _CASE)


def _invite(embargo: Any) -> Any:
    return em_propose_embargo_activity(
        embargo,
        context=_CASE,
        id_=f"{_CASE}/activities/invite",
        actor=_SENDER,
        to=[_MANAGER],
    )


def _request(
    use_case: type, embargo: Any, *, malformed: bool, make_payload: Any
) -> Any:
    """The late activity, from _SENDER to the CASE_MANAGER."""
    if use_case is AcceptInviteToEmbargoOnCaseReceivedUseCase:
        activity = em_accept_embargo_activity(
            _invite(embargo), context=_CASE, actor=_SENDER, to=[_MANAGER]
        )
    else:
        activity = _invite(embargo)
    event = make_payload(activity, receiving_actor_id=_MANAGER)
    if malformed:
        # An Invite that names no embargo (EP-09-010).
        event = event.model_copy(update={"object_": None})
        assert not event.object_id
    return event


def _ledger(dl: SqliteDataLayer) -> list[object]:
    return list(dl.list_objects("CaseLedgerEntry"))


@pytest.mark.spec("CM-23-013")
@pytest.mark.spec("CM-23-017")
@pytest.mark.parametrize(
    ("use_case", "malformed"),
    [
        (AcceptInviteToEmbargoOnCaseReceivedUseCase, False),
        (InviteToEmbargoOnCaseReceivedUseCase, False),
        # A malformed Invite is answered with a ProcessingFault on an open
        # case; after close it is not answered at all.
        (InviteToEmbargoOnCaseReceivedUseCase, True),
    ],
    ids=["accept", "invite", "malformed-invite"],
)
def test_a_late_embargo_activity_is_refused_before_any_write(
    use_case, malformed, make_payload
):
    dl, _actor, _case, embargo = make_embargo_case_with_actor(
        _CASE, _SENDER, case_manager_actor_id=_MANAGER
    )
    _close(dl)
    ledger_before = len(_ledger(dl))
    outbox_before = list(dl.outbox_list())

    result = use_case(
        dl,
        _request(
            use_case, embargo, malformed=malformed, make_payload=make_payload
        ),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CM-23-013" in (result.reason or "")
    assert len(_ledger(dl)) == ledger_before
    assert list(dl.outbox_list()) == outbox_before
