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

"""The factory owns the closing-act check of a received tree (CM-23-018).

A tree whose act would close its sender passes ``closing_act=True``; the
factory places the closed-sender check just before the sender guard, inside
the one tree (CLP-10-005, ADR-0135), and the handler reads a repeat as
``SKIPPED`` (ID-05-003).  The end-to-end dispositions are driven through the
handlers in ``test_case_joining_replies.py``,
``test_full_case_invite_rm_declaration.py`` and
``test_rm_declaration_adjudication.py``.
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.case_lookup import (
    RequireCaseForReport,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderClosureNotRecordedNode,
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import (
    LedgerActivityContext,
    SenderCheckContext,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received._bt_verdict import closing_act_repeat
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/case-closing-act-001"
SENDER_ID = "https://example.org/actors/closing-sender"
RULE = SenderRule.in_case(SenderEntitlementKind.PARTICIPANT)


def _context(case_id: str | None = CASE_ID) -> SenderCheckContext:
    return SenderCheckContext(sender_id=SENDER_ID, case_id=case_id)


def _closing_tree(
    case_id: str | None = CASE_ID,
    case_resolution: list[py_trees.behaviour.Behaviour] | None = None,
) -> ReceivedActivityTree:
    return create_receive_activity_tree(
        name="ClosingBT",
        case_id=case_id,
        precondition_guards=[],
        sender_rule=RULE,
        sender_context=_context(case_id),
        closing_act=True,
        case_resolution=case_resolution,
    )


def _checks(
    tree: py_trees.behaviour.Behaviour,
) -> list[SenderClosureNotRecordedNode]:
    return [
        n
        for n in tree.iterate()
        if isinstance(n, SenderClosureNotRecordedNode)
    ]


class TestPlacement:
    @pytest.mark.spec("CM-23-018")
    @pytest.mark.spec("CLP-10-010")
    def test_the_check_runs_just_before_the_sender_guard(self) -> None:
        tree = _closing_tree(
            case_resolution=[RequireCaseForReport(report_id="urn:r")]
        )

        names = [child.name for child in tree.children]
        check = names.index("SenderClosureNotRecordedNode")
        assert names[check - 1] == "RequireCaseForReport"
        assert names[check + 1] == "SenderIsParticipantNode"
        assert names.index("CaseOpenToExternalWrites") < check

    def test_the_check_is_a_door_guard_on_the_senders_case(self) -> None:
        tree = _closing_tree()

        (check,) = _checks(tree)
        assert check in tree.door_guards
        assert check.case_id == CASE_ID
        assert check.sender_actor_id == SENDER_ID

    def test_a_tree_that_closes_no_one_has_no_check(self) -> None:
        tree = create_receive_activity_tree(
            name="OtherBT",
            case_id=CASE_ID,
            precondition_guards=[],
            sender_rule=RULE,
            sender_context=_context(),
        )

        assert _checks(tree) == []
        assert tree.repeated_closing_act is None

    def test_an_act_on_no_case_has_no_closure_to_repeat(self) -> None:
        tree = _closing_tree(case_id=None)

        assert _checks(tree) == []
        assert tree.repeated_closing_act is None


class TestWiring:
    def test_a_closing_act_needs_a_sender_guard(self) -> None:
        with pytest.raises(VultronWiringError, match="closing_act"):
            create_receive_activity_tree(
                name="ClosingBT",
                case_id=CASE_ID,
                precondition_guards=[],
                closing_act=True,
            )

    def test_a_ledger_activity_names_no_sender_at_build_time(self) -> None:
        with pytest.raises(VultronWiringError, match="closing_act"):
            create_receive_activity_tree(
                name="ClosingBT",
                case_id=None,
                precondition_guards=[],
                sender_rule=SenderRule.in_case(
                    SenderEntitlementKind.CASE_MANAGER
                ),
                sender_context=LedgerActivityContext(),
                closing_act=True,
            )


class TestRepeatVerdict:
    def _run_check(
        self, tree: ReceivedActivityTree, *, sender_closed: bool
    ) -> None:
        (check,) = _checks(tree)
        check.status = Status.FAILURE
        check.sender_closed = sender_closed
        check.feedback_message = (
            f"'{SENDER_ID}' is already closed on case '{CASE_ID}' (CM-23-018)"
        )

    @pytest.mark.spec("CM-23-018")
    @pytest.mark.spec("ID-05-003")
    def test_a_recorded_closure_reads_as_a_skipped_repeat(self) -> None:
        tree = _closing_tree()
        self._run_check(tree, sender_closed=True)

        verdict = closing_act_repeat(tree)

        assert verdict is not None
        assert verdict.disposition is HandlerDisposition.SKIPPED
        assert verdict.reason == (
            f"ClosingBT: '{SENDER_ID}' is already closed on case"
            f" '{CASE_ID}' (CM-23-018) — a repeat of a closing act, nothing"
            " to apply (ID-05-003)"
        )

    def test_a_check_that_did_not_find_a_closure_is_no_repeat(self) -> None:
        tree = _closing_tree()
        self._run_check(tree, sender_closed=False)

        assert closing_act_repeat(tree) is None

    def test_a_check_that_never_ran_is_no_repeat(self) -> None:
        assert closing_act_repeat(_closing_tree()) is None

    def test_a_tree_not_built_by_the_factory_is_a_wiring_error(self) -> None:
        tree = py_trees.composites.Sequence(name="AdHoc", memory=False)

        with pytest.raises(VultronWiringError, match="received-activity"):
            closing_act_repeat(tree)
