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
"""Factories for the full-case Invite and its replies (VAM-04-011..014, AF-02-003).

The ledger position travels in ``content`` as the ``LedgerPosition`` model's
own JSON dump, and only the factories produce that string.
"""

import json

import pytest

from vultron.core.models.ledger_position import LedgerPosition
from vultron.wire.as2.factories import (
    rm_accept_full_case_invite_activity,
    rm_invite_to_full_case_activity,
    rm_reject_full_case_invite_activity,
    rm_tentative_reject_full_case_invite_activity,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.base.objects.actors import as_Organization

_CASE = "https://example.org/cases/full-factories"
_MANAGER = "https://example.org/actors/manager"
_INVITEE = "https://example.org/actors/invitee"
_FLOOR = LedgerPosition(log_index=2, entry_hash="cd" * 32)
_OWN = LedgerPosition(log_index=5, entry_hash="ef" * 32)


def _invite():
    return rm_invite_to_full_case_activity(
        as_Organization(id_=_INVITEE),
        _CASE,
        _FLOOR,
        actor=_MANAGER,
        to=[_INVITEE],
    )


@pytest.mark.spec("VAM-04-011")
def test_invite_targets_the_plain_case_uri_and_carries_the_floor_in_content():
    invite = _invite()

    dumped = json.loads(
        invite.model_dump_json(by_alias=True, exclude_none=True)
    )
    assert dumped["target"] == _CASE
    assert dumped["context"] == _CASE
    assert json.loads(dumped["content"]) == {
        "logIndex": 2,
        "entryHash": "cd" * 32,
    }
    assert "ledgerTail" not in dumped


@pytest.mark.spec("VAM-04-012")
@pytest.mark.spec("VAM-04-013")
@pytest.mark.spec("VAM-04-014")
@pytest.mark.parametrize(
    ("build", "kind"),
    [
        (rm_accept_full_case_invite_activity, "Accept"),
        (rm_tentative_reject_full_case_invite_activity, "TentativeReject"),
        (rm_reject_full_case_invite_activity, "Reject"),
    ],
)
def test_replies_carry_the_repliers_position_in_content(build, kind):
    invite = _invite()

    reply = build(invite, _OWN, actor=_INVITEE)

    dumped = json.loads(
        reply.model_dump_json(by_alias=True, exclude_none=True)
    )
    assert dumped["type"] == kind
    assert dumped["inReplyTo"] == invite.id_
    assert LedgerPosition.model_validate_json(dumped["content"]) == _OWN
    assert "ledgerTail" not in dumped


@pytest.mark.spec("VAM-04-011")
def test_a_non_full_case_invite_cannot_be_answered():
    from vultron.wire.as2.factories import rm_invite_to_case_activity
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCaseStub,
    )

    stub_invite = rm_invite_to_case_activity(
        as_Organization(id_=_INVITEE),
        target=as_VulnerabilityCaseStub(case_id=_CASE, summary="a case"),
        actor=_MANAGER,
    )

    with pytest.raises(VultronActivityConstructionError):
        rm_accept_full_case_invite_activity(stub_invite, _OWN, actor=_INVITEE)
