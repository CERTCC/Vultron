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
"""
Unit tests for vultron.errors — BtNodePreconditionError.

Spec coverage:
- ADR-0032 / BT-HELPER-01: BT node helpers raise BtNodePreconditionError
  instead of returning None; update() is the single try/except handler.
"""

import pytest

from vultron.errors import BtNodePreconditionError, VultronError


def test_bt_node_precondition_error_is_vultron_error():
    """BtNodePreconditionError must inherit from VultronError (ADR-0032)."""
    assert issubclass(BtNodePreconditionError, VultronError)


def test_bt_node_precondition_error_is_exception():
    """BtNodePreconditionError must be a standard Exception subclass."""
    assert issubclass(BtNodePreconditionError, Exception)


def test_bt_node_precondition_error_can_be_raised_with_message():
    """BtNodePreconditionError carries the message string (BT-HELPER-01)."""
    import re

    msg = "case 'abc' not in blackboard"
    with pytest.raises(BtNodePreconditionError, match=re.escape(msg)):
        raise BtNodePreconditionError(msg)


def test_bt_node_precondition_error_message_preserved():
    """str(exc) returns the original message."""
    msg = "blackboard entry 'x' is not a VulnerabilityCase"
    try:
        raise BtNodePreconditionError(msg)
    except BtNodePreconditionError as exc:
        assert str(exc) == msg


def test_bt_node_precondition_error_is_catchable_as_vultron_error():
    """BtNodePreconditionError is catchable as VultronError (ADR-0032)."""
    with pytest.raises(VultronError):
        raise BtNodePreconditionError("precondition failed")


def test_bt_node_precondition_error_supports_chained_cause():
    """BtNodePreconditionError supports exception chaining via __cause__."""
    original = KeyError("missing_key")
    try:
        raise BtNodePreconditionError("key missing") from original
    except BtNodePreconditionError as exc:
        assert exc.__cause__ is original


def test_update_catches_bt_node_precondition_error():
    """update() pattern: helper raises, update() sets feedback_message and returns FAILURE.

    This is the canonical BT-HELPER-01 usage pattern from ADR-0032.
    The test uses a stub class with a ``feedback_message`` attribute to verify
    that the catch site assigns ``self.feedback_message = str(e)``, which is
    the mechanism BT infrastructure uses to surface failure reasons.
    """
    from py_trees.common import Status

    class _StubNode:
        feedback_message: str = ""

        def _helper_that_raises(self) -> str:
            raise BtNodePreconditionError("case not on blackboard")

        def update(self) -> Status:
            try:
                self._helper_that_raises()
                return Status.SUCCESS
            except BtNodePreconditionError as e:
                self.feedback_message = str(e)
                return Status.FAILURE

    node = _StubNode()
    status = node.update()
    assert status == Status.FAILURE
    assert node.feedback_message == "case not on blackboard"
