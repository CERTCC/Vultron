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

"""Tests for ``vultron.core.behaviors.node_logger`` (SL-01-005)."""

import logging

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.node_logger import node_logger


class _PlainNode(py_trees.behaviour.Behaviour):
    def update(self) -> Status:
        return Status.SUCCESS


def test_returns_stdlib_logger_named_after_node_class() -> None:
    node = _PlainNode(name="plain")
    resolved = node_logger(node)
    assert isinstance(resolved, logging.Logger)
    assert resolved.name == f"{__name__}._PlainNode"


def test_plain_py_trees_logger_is_not_stdlib() -> None:
    """The premise: a plain node's own logger cannot take lazy args."""
    node = _PlainNode(name="plain")
    assert not isinstance(node.logger, logging.Logger)
    with pytest.raises(TypeError):
        node.logger.debug("tick %s", 1)  # type: ignore[call-arg]


def test_rebinding_node_shares_the_resolved_logger() -> None:
    node = DataLayerAction(name="action")
    assert node.logger is node_logger(node)


@pytest.mark.spec("SL-01-005")
def test_lazy_args_render_through_resolved_logger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    node = _PlainNode(name="plain")
    log = node_logger(node)
    with caplog.at_level(logging.DEBUG, logger=log.name):
        log.debug("%s: tick %s", node.name, 3)
    record = caplog.records[-1]
    assert record.msg == "%s: tick %s"
    assert record.getMessage() == "plain: tick 3"
