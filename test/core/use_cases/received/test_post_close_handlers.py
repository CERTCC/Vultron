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

The factory's post-close guard stops a received tree before its commit, but a
handler can commit, send an ER or answer with a ProcessingFault before its
tree runs, or after reading the tree's failure.  After ``case_fully_closed``
none of that may happen: the activity is ``REFUSED``, nothing is recorded and
nothing is sent (CM-23-013, CM-23-017).
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
)

from .conftest import make_embargo_case_with_actor

_CASE = "https://example.org/cases/post-close-handlers"
_MANAGER = "https://example.org/users/pc-coord"
_SENDER = "https://example.org/users/pc-vendor"


def _close(dl: SqliteDataLayer) -> None:
    dl.create(
        _to_persistable_entry(
            HashChainLedgerRecord(
                case_id=_CASE,
                log_index=0,
                object_id=f"{_CASE}/activities/owner-leave",
                event_type="case_fully_closed",
                payload_snapshot={"actor": _SENDER},
                prev_log_hash="0" * 64,
            )
        )
    )


def _request(embargo: Any, *, embargo_id: str | None) -> MagicMock:
    request = MagicMock()
    request.receiving_actor_id = _MANAGER
    request.actor_id = _SENDER
    request.activity_id = f"{_CASE}/activities/late"
    request.activity.to = [_MANAGER]
    request.activity.cc = []
    request.case_id = _CASE
    request.context_id = _CASE
    request.embargo_id = embargo_id
    request.object_id = embargo_id
    request.embargo = embargo
    request.object_type = "EmbargoEvent"
    request.invite_id = f"{_CASE}/activities/invite"
    request.invitee_id = _MANAGER
    request.to_recipients = [_MANAGER]
    return request


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
    use_case, malformed
):
    dl, _actor, _case, embargo = make_embargo_case_with_actor(
        _CASE, _SENDER, case_manager_actor_id=_MANAGER
    )
    _close(dl)
    ledger_before = len(_ledger(dl))
    outbox_before = list(dl.outbox_list())

    result = use_case(
        dl,
        _request(embargo, embargo_id=None if malformed else embargo.id_),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CM-23-013" in (result.reason or "")
    assert len(_ledger(dl)) == ledger_before
    assert list(dl.outbox_list()) == outbox_before
