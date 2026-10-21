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

import importlib
import inspect
import pkgutil
import re

import py_trees
import pytest
from py_trees.common import Status

import vultron.core.behaviors as behaviors_pkg
from vultron.core.behaviors.case.nodes.announce import CaseCopyNotStaleNode
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
    FlaggedRepeatGuardMixin,
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
    (CaseCopyNotStaleNode, "is_stale"),
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


_REPEAT_FLAG_WRITE = re.compile(
    r"self\.(is_repeat|is_redelivery|is_duplicate|is_stale)\s*="
)


def _behavior_classes() -> list[type]:
    found: list[type] = []
    for info in pkgutil.walk_packages(
        behaviors_pkg.__path__, behaviors_pkg.__name__ + "."
    ):
        module = importlib.import_module(info.name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ == module.__name__ and issubclass(
                cls, py_trees.behaviour.Behaviour
            ):
                found.append(cls)
    return found


@pytest.mark.spec("CLP-10-022")
def test_every_guard_that_flags_a_repeat_reports_it():
    """Ratchet: a guard a handler reads as ``SKIPPED`` tells the refusal stage.

    A guard that sets a repeat flag but does not implement
    ``ReportsIdempotentRepeat`` would have its repeat answered with a refusal
    notice, contradicting the effect already in place (CLP-05-001).
    """
    classes = _behavior_classes()
    flagged = [
        cls
        for cls in classes
        if _REPEAT_FLAG_WRITE.search(inspect.getsource(cls))
    ]
    assert len(classes) > 100, "the scan found too few behavior classes"
    assert {cls for cls, _ in _FLAGGED} <= set(flagged), (
        "the scan missed a known repeat guard"
    )
    missing = sorted(
        cls.__qualname__
        for cls in flagged
        if not isinstance(getattr(cls, "failed_as_repeat", None), property)
    )
    assert missing == [], (
        f"{missing} set a repeat flag but do not report it: inherit"
        " FlaggedRepeatGuardMixin and name the flag in _REPEAT_FLAG"
    )


@pytest.mark.spec("CLP-10-022")
def test_every_flagged_repeat_guard_names_the_flag_it_sets():
    """Ratchet: ``FlaggedRepeatGuardMixin`` reads the flag ``_REPEAT_FLAG`` names.

    A subclass that omits it inherits ``failed_as_repeat`` and so passes the
    ratchet above, then raises ``AttributeError`` on its first refusal.
    """
    wrong = sorted(
        cls.__qualname__
        for cls in _behavior_classes()
        if issubclass(cls, FlaggedRepeatGuardMixin)
        and getattr(cls, "_REPEAT_FLAG", None)
        not in set(_REPEAT_FLAG_WRITE.findall(inspect.getsource(cls)))
    )
    assert wrong == [], (
        f"{wrong} inherit FlaggedRepeatGuardMixin but _REPEAT_FLAG does not"
        " name a repeat flag the guard sets"
    )
