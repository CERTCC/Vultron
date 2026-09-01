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
from types import SimpleNamespace

import pytest

from vultron.core.states.cs import CS_pxa
from vultron.core.behaviors.status.nodes.threat_termination import (
    _ThreatTerminationSkipConditionNode,
)


def _node(case_status: object) -> _ThreatTerminationSkipConditionNode:
    return _ThreatTerminationSkipConditionNode(
        status_obj=SimpleNamespace(case_status=case_status),
        case_id="case-1",
    )


def test_threat_present_handles_unset_pxa():
    """A participant with no PXA dimension has asserted no threat."""
    assert _node(SimpleNamespace(pxa=None))._threat_present() is False


def test_threat_present_false_for_empty_pxa_state():
    assert (
        _node(
            SimpleNamespace(pxa=SimpleNamespace(state=CS_pxa.pxa))
        )._threat_present()
        is False
    )


@pytest.mark.parametrize("state", [CS_pxa.Pxa, CS_pxa.pXa, CS_pxa.pxA])
def test_threat_present_true_when_a_dimension_is_set(state):
    assert (
        _node(
            SimpleNamespace(pxa=SimpleNamespace(state=state))
        )._threat_present()
        is True
    )
