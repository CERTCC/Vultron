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

"""The VINCE example is a case reader and nothing else (#6358).

Spec: ARCH-05-004, ARCH-05-005, CRD-02-004.
"""

import pytest

from test.support.connector_ports import surplus_members
from vultron.adapters.connectors.base import ports_implemented_by
from vultron.adapters.connectors.example.vince import (
    VINCE_UNOBSERVABLE,
    VinceCaseReader,
)
from vultron.core.ports.case_reader import CaseReader


@pytest.mark.spec("ARCH-05-004")
def test_the_vince_example_implements_the_case_reader_port_only():
    assert ports_implemented_by(VinceCaseReader()) == (CaseReader,)


@pytest.mark.spec("ARCH-05-005")
def test_the_vince_example_exposes_no_member_of_a_port_it_lacks():
    assert surplus_members(VinceCaseReader()) == set()


@pytest.mark.spec("CRD-02-004")
def test_the_vince_example_declares_what_vince_cannot_observe():
    assert VinceCaseReader().unobservable == VINCE_UNOBSERVABLE
    assert VINCE_UNOBSERVABLE


def test_the_vince_example_reads_nothing_yet():
    with pytest.raises(NotImplementedError, match="#5963"):
        VinceCaseReader().read_case("VU#000000")
