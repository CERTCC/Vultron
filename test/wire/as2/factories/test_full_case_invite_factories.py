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

The ledger position travels as the activity's ``ledgerPosition``, the
property every case activity states (SYNC-18-001), not in ``content``.
"""

import json

import pytest

from test.support.objects import authored_at, make
from vultron.core.models.ledger_position import LedgerPosition
from vultron.wire.as2.factories import (
    rm_accept_full_case_invite_activity,
    rm_invite_to_full_case_activity,
    rm_reject_full_case_invite_activity,
    rm_tentative_reject_full_case_invite_activity,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.base.objects.actors import as_Organization
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE = "https://example.org/cases/full-factories"
_MANAGER = "https://example.org/actors/manager"
_INVITEE = "https://example.org/actors/invitee"
_FLOOR = LedgerPosition(log_index=2, entry_hash="cd" * 32)
_OWN = LedgerPosition(log_index=5, entry_hash="ef" * 32)


def _case() -> as_VulnerabilityCase:
    return make(
        as_VulnerabilityCase,
        id_=_CASE,
        name="Full factories",
        attributed_to=_MANAGER,
        stub_summary="a case",
    )


def _invite():
    return rm_invite_to_full_case_activity(
        make(as_Organization, id_=_INVITEE),
        _case(),
        _FLOOR,
        actor=_MANAGER,
        to=[_INVITEE],
        at=authored_at(),
    )


@pytest.mark.spec("VAM-04-011")
@pytest.mark.spec("SYNC-18-001")
def test_invite_carries_the_whole_case_and_the_floor_as_position():
    invite = _invite()

    dumped = json.loads(
        invite.model_dump_json(by_alias=True, exclude_none=True)
    )
    assert dumped["object"]["type"] == "VulnerabilityCase"
    assert dumped["object"]["id"] == _CASE
    assert dumped["target"]["id"] == _INVITEE
    assert dumped["context"] == _CASE
    assert dumped["ledgerPosition"] == {
        "logIndex": 2,
        "entryHash": "cd" * 32,
    }
    assert "content" not in dumped
    assert "ledgerTail" not in dumped


@pytest.mark.spec("VAM-04-012")
@pytest.mark.spec("VAM-04-013")
@pytest.mark.spec("VAM-04-014")
@pytest.mark.spec("SYNC-18-001")
@pytest.mark.parametrize(
    ("build", "kind"),
    [
        (rm_accept_full_case_invite_activity, "Accept"),
        (rm_tentative_reject_full_case_invite_activity, "TentativeReject"),
        (rm_reject_full_case_invite_activity, "Reject"),
    ],
)
def test_replies_carry_the_repliers_position_as_position(build, kind):
    invite = _invite()

    reply = build(invite, _OWN, actor=_INVITEE, at=authored_at())

    dumped = json.loads(
        reply.model_dump_json(by_alias=True, exclude_none=True)
    )
    assert dumped["type"] == kind
    assert dumped["inReplyTo"] == invite.id_
    assert LedgerPosition.model_validate(dumped["ledgerPosition"]) == _OWN
    assert "content" not in dumped
    assert "ledgerTail" not in dumped


@pytest.mark.spec("VAM-04-011")
@pytest.mark.spec("AF-04-001")
def test_the_full_case_invite_refuses_a_bare_case_uri():
    """The Invite carries the case whole, so a URI is refused (ADR-0205)."""
    with pytest.raises(VultronActivityConstructionError, match="ADR-0205"):
        rm_invite_to_full_case_activity(
            make(as_Organization, id_=_INVITEE),
            _CASE,  # type: ignore[arg-type]
            _FLOOR,
            actor=_MANAGER,
            at=authored_at(),
        )


@pytest.mark.spec("VAM-04-011")
def test_a_non_full_case_invite_cannot_be_answered():
    from vultron.wire.as2.factories import rm_invite_to_case_activity

    stub_invite = rm_invite_to_case_activity(
        make(as_Organization, id_=_INVITEE),
        case=_case(),
        actor=_MANAGER,
        at=authored_at(),
    )

    with pytest.raises(VultronActivityConstructionError):
        rm_accept_full_case_invite_activity(
            stub_invite, _OWN, actor=_INVITEE, at=authored_at()
        )
