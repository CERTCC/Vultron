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

"""Every guard whose failure the handler reports ``SKIPPED`` says so.

The refusal stage sends no refusal effect for a guard's failure that is an
idempotent repeat (CLP-10-022, CLP-05-001).  It reads that from the guard
through :class:`~vultron.core.behaviors.idempotency.ReportsIdempotentRepeat`,
so each guard the handlers read as a repeat must implement it, and report a
repeat only when it failed as one.
"""

import pytest
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.invite_participant import (
    CheckInviteeNotAlreadyParticipantNode,
)
from vultron.core.behaviors.case.nodes.ownership_offer_guard import (
    NoOpenOwnershipOfferNode,
    OwnershipOfferOpenNode,
)
from vultron.core.behaviors.case.nodes.reference_list import (
    CaseReferenceEditPendingNode,
)
from vultron.core.behaviors.case.nodes.role_offer_guard import (
    RoleOfferAdmissibleNode,
)
from vultron.core.behaviors.embargo.nodes.answer_repeat import (
    EmbargoAnswerNotRecordedNode,
)
from vultron.core.behaviors.embargo.nodes.withdrawal import (
    IsWithdrawableEmbargoNode,
)
from vultron.core.behaviors.idempotency import (
    ReportsIdempotentRepeat,
    SilentIdempotencyGuardMixin,
)

#: Each guard a handler reads as a repeat, and the flag it sets on one.
_FLAGGED = [
    (EmbargoAnswerNotRecordedNode, "is_repeat"),
    (IsWithdrawableEmbargoNode, "is_redelivery"),
    (NoOpenOwnershipOfferNode, "is_redelivery"),
    (OwnershipOfferOpenNode, "is_redelivery"),
    (RoleOfferAdmissibleNode, "is_redelivery"),
    (CaseReferenceEditPendingNode, "is_duplicate"),
]


def _bare(cls: type, **attrs: object) -> object:
    """An instance with only the attributes ``failed_as_repeat`` reads."""
    node: object = object.__new__(cls)
    for key, value in attrs.items():
        setattr(node, key, value)
    return node


@pytest.mark.spec("CLP-10-022")
@pytest.mark.parametrize(
    ("cls", "flag"), _FLAGGED, ids=[c.__name__ for c, _ in _FLAGGED]
)
@pytest.mark.parametrize(
    ("flagged", "status", "expected"),
    [
        (True, Status.FAILURE, True),
        (False, Status.FAILURE, False),
        (True, Status.SUCCESS, False),
    ],
    ids=["repeat", "refusal", "admitted"],
)
def test_a_flagged_guard_reports_a_repeat_only_when_it_failed_as_one(
    cls: type, flag: str, flagged: bool, status: Status, expected: bool
):
    node = _bare(cls, **{flag: flagged, "status": status})

    assert isinstance(node, ReportsIdempotentRepeat)
    assert node.failed_as_repeat is expected


@pytest.mark.spec("CLP-10-022")
def test_a_silent_idempotency_guard_reports_its_repeat():
    assert issubclass(
        CheckInviteeNotAlreadyParticipantNode, SilentIdempotencyGuardMixin
    )
    node = _bare(
        CheckInviteeNotAlreadyParticipantNode,
        _repeat_detected=True,
        status=Status.FAILURE,
    )

    assert isinstance(node, ReportsIdempotentRepeat)
    assert node.failed_as_repeat
