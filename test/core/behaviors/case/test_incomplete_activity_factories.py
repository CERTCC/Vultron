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
"""A received tree factory refuses a missing field in the tree (CLP-10-018).

Each factory below is handed an activity missing a value its tree needs (the
inline object, the case, an id the tree keys on) and returns the
incomplete-activity tree: the doors and intake, then one
:class:`~vultron.core.behaviors.case.nodes.incomplete_activity.ActivityIncompleteNode`
whose reason is the one the use case's ``execute()`` used to return before
any tree ran (#6493).  ``execute()`` itself refuses nothing:
``test/architecture/test_received_use_case_execute.py`` pins that.
"""

from collections.abc import Callable
from typing import Any

import py_trees
import pytest

from test.support.objects import make
from vultron.core.behaviors.case.accept_case_proposal_received_tree import (
    create_accept_case_proposal_received_tree,
)
from vultron.core.behaviors.case.accept_invite_tree import (
    create_accept_invite_actor_to_case_tree,
)
from vultron.core.behaviors.case.add_report_received_tree import (
    create_add_report_to_case_received_tree,
)
from vultron.core.behaviors.case.create_case_received_tree import (
    create_create_case_received_tree,
)
from vultron.core.behaviors.case.full_case_invite_trees import (
    create_full_case_invite_reply_received_tree,
    create_invite_actor_to_full_case_received_tree,
)
from vultron.core.behaviors.case.invite_actor_to_case_received_tree import (
    create_invite_actor_to_case_received_tree,
    create_reject_invite_actor_to_case_received_tree,
)
from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityIncompleteNode,
)
from vultron.core.behaviors.case.reject_case_proposal_received_tree import (
    create_reject_case_proposal_received_tree,
)
from vultron.core.behaviors.note.add_note_received_tree import (
    create_add_note_to_case_received_tree,
)
from vultron.core.behaviors.report.received_report_trees.validate import (
    create_validate_report_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sync.announce_tree.factory import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.read_tree import create_read_log_entry_tree
from vultron.core.behaviors.sync.reject_tree import (
    create_reject_log_entry_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.note import VultronNote
from vultron.core.states.rm import RM

_BASE = "https://example.org"
_CASE = f"{_BASE}/cases/case"
_ACTOR = f"{_BASE}/actors/sender"
_INVITE = f"{_CASE}/invitations/1"
_REPORT = f"{_BASE}/reports/r"
_POSITION = LedgerPosition(log_index=0, entry_hash="0" * 64)

#: Any composable rule: the guard under test is not the sender guard.
_RULE = SenderRule.in_case(SenderEntitlementKind.CASE_MANAGER)


def _note() -> VultronNote:
    return make(VultronNote, id_=f"{_BASE}/notes/n", content="x")


def _case() -> VulnerabilityCase:
    return make(VulnerabilityCase, id_=_CASE, attributed_to=_ACTOR)


_Factory = Callable[..., py_trees.behaviour.Behaviour]


def _param(
    factory: _Factory,
    kwargs: dict[str, Any],
    missing: str,
    reason: str,
    *,
    absent: Any = None,
) -> Any:
    """One factory call missing *missing* (set to *absent*), and its reason.

    *kwargs* holds the complete call, *missing* included, so the same case
    checks that the guard is gone once the value is present.
    """
    return pytest.param(
        factory,
        {"sender_rule": _RULE, **kwargs},
        missing,
        absent,
        reason,
        id=f"{factory.__name__}-{missing}",
    )


_NOTE_REASON = (
    "Add(Note)[target=VulnerabilityCase] is missing its inline note or case id"
)
_INVITE_REASON = "Invite is missing its case id or invitee id"
_ACCEPT_INVITE_REASON = (
    "Accept(Invite) is missing its case id, invitee id or Invite id"
)
_REJECT_INVITE_REASON = "Reject(Invite) is missing its case id or Invite id"
_ADD_REPORT_REASON = (
    "Add(VulnerabilityReport)[target=VulnerabilityCase] is missing its"
    " report id or case id"
)
_VALIDATE_REASON = (
    "Accept(Offer(VulnerabilityReport)) is missing its report id or offer id"
)
_REPLY_REASON = "reply is missing its case id or Invite id"


def _cases() -> list[Any]:
    note = {
        "note_obj": _note(),
        "case_id": _CASE,
        "sender_id": _ACTOR,
        "activity_id": f"{_BASE}/activities/a",
    }
    invite = {
        "case_id": _CASE,
        "invitee_id": _ACTOR,
        "inviter_id": _ACTOR,
        "invite_id": _INVITE,
    }
    accept = {
        "case_id": _CASE,
        "invitee_id": _ACTOR,
        "invite_id": _INVITE,
        "embedded_invitee_id": _ACTOR,
    }
    reject = {"case_id": _CASE, "invite_id": _INVITE, "invitee_id": _ACTOR}
    add_report = {"report_id": _REPORT, "case_id": _CASE, "sender_id": _ACTOR}
    validate = {
        "report_id": _REPORT,
        "offer_id": f"{_BASE}/offers/o",
        "sender_actor_id": _ACTOR,
    }
    create_case = {"case_obj": _case(), "case_id": _CASE, "sender_id": _ACTOR}
    full_invite = {
        "case_id": _CASE,
        "invitee_id": _ACTOR,
        "inviter_id": _ACTOR,
        "floor": _POSITION,
    }
    reply = {
        "name": "AcceptFullCaseInviteBT",
        "case_id": _CASE,
        "invite_id": _INVITE,
        "replier_id": _ACTOR,
        "position": _POSITION,
        "rm_state": RM.ACCEPTED,
    }
    read = {"case_id": _CASE, "sender_id": _ACTOR}
    return [
        _param(
            create_add_note_to_case_received_tree,
            note,
            "note_obj",
            _NOTE_REASON,
        ),
        _param(
            create_add_note_to_case_received_tree,
            note,
            "case_id",
            _NOTE_REASON,
        ),
        _param(
            create_invite_actor_to_case_received_tree,
            invite,
            "case_id",
            _INVITE_REASON,
        ),
        _param(
            create_invite_actor_to_case_received_tree,
            invite,
            "invitee_id",
            _INVITE_REASON,
        ),
        _param(
            create_accept_invite_actor_to_case_tree,
            accept,
            "case_id",
            _ACCEPT_INVITE_REASON,
        ),
        _param(
            create_accept_invite_actor_to_case_tree,
            accept,
            "embedded_invitee_id",
            _ACCEPT_INVITE_REASON,
        ),
        _param(
            create_accept_invite_actor_to_case_tree,
            accept,
            "invite_id",
            _ACCEPT_INVITE_REASON,
        ),
        _param(
            create_reject_invite_actor_to_case_received_tree,
            reject,
            "case_id",
            _REJECT_INVITE_REASON,
        ),
        _param(
            create_reject_invite_actor_to_case_received_tree,
            reject,
            "invite_id",
            _REJECT_INVITE_REASON,
        ),
        _param(
            create_add_report_to_case_received_tree,
            add_report,
            "report_id",
            _ADD_REPORT_REASON,
        ),
        _param(
            create_add_report_to_case_received_tree,
            add_report,
            "case_id",
            _ADD_REPORT_REASON,
        ),
        _param(
            create_validate_report_received_tree,
            validate,
            "report_id",
            _VALIDATE_REASON,
        ),
        _param(
            create_validate_report_received_tree,
            validate,
            "offer_id",
            _VALIDATE_REASON,
        ),
        _param(
            create_create_case_received_tree,
            create_case,
            "case_obj",
            "Create(VulnerabilityCase) carries no case object",
        ),
        _param(
            create_create_case_received_tree,
            create_case,
            "case_id",
            "Create(VulnerabilityCase) case object has no id",
        ),
        _param(
            create_accept_case_proposal_received_tree,
            {"report_id": _REPORT, "case_actor_id": _ACTOR},
            "report_id",
            "Accept(CaseProposal) carries no inline report",
        ),
        _param(
            create_reject_case_proposal_received_tree,
            {"report_id": _REPORT, "sender_actor_id": _ACTOR},
            "report_id",
            "Reject(CaseProposal) carries no inline report",
        ),
        _param(
            create_invite_actor_to_full_case_received_tree,
            full_invite,
            "case_id",
            _INVITE_REASON,
        ),
        _param(
            create_invite_actor_to_full_case_received_tree,
            full_invite,
            "invitee_id",
            _INVITE_REASON,
        ),
        _param(
            create_full_case_invite_reply_received_tree,
            reply,
            "case_id",
            _REPLY_REASON,
        ),
        _param(
            create_full_case_invite_reply_received_tree,
            reply,
            "invite_id",
            _REPLY_REASON,
        ),
        _param(
            create_reject_log_entry_tree,
            {"case_id": _CASE},
            "case_id",
            "Reject(CaseLedgerEntry) names neither a log entry nor a case",
        ),
        _param(
            create_read_log_entry_tree,
            read,
            "case_id",
            "Read(CaseLedgerEntry) names no case in its context",
        ),
        _param(
            create_announce_log_entry_tree,
            {"carries_entry": True},
            "carries_entry",
            "Announce(CaseLedgerEntry) carries no log entry",
            absent=False,
        ),
    ]


def _incomplete_guards(
    tree: py_trees.behaviour.Behaviour,
) -> list[ActivityIncompleteNode]:
    return [n for n in tree.iterate() if isinstance(n, ActivityIncompleteNode)]


@pytest.mark.spec("CLP-10-018")
@pytest.mark.parametrize(
    ("factory", "kwargs", "missing", "absent", "reason"), _cases()
)
def test_a_missing_field_gets_the_incomplete_activity_guard(
    factory: _Factory,
    kwargs: dict[str, Any],
    missing: str,
    absent: Any,
    reason: str,
) -> None:
    """The factory's tree refuses the incomplete activity, for its reason."""
    guards = _incomplete_guards(factory(**{**kwargs, missing: absent}))
    assert [g.reason for g in guards] == [reason]


@pytest.mark.spec("CLP-10-018")
@pytest.mark.parametrize(
    ("factory", "kwargs", "missing", "absent", "reason"), _cases()
)
def test_a_complete_activity_gets_no_incomplete_activity_guard(
    factory: _Factory,
    kwargs: dict[str, Any],
    missing: str,
    absent: Any,
    reason: str,
) -> None:
    """With every value present, the guard is gone: the incomplete tree is
    the answer to the missing value alone."""
    del missing, absent, reason
    assert _incomplete_guards(factory(**kwargs)) == []
