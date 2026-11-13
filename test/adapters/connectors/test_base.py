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

"""A connector plugin is a name plus the core ports it implements (#6358).

Spec: ARCH-05-004, ARCH-05-005.
"""

from typing import get_protocol_members

import pytest

from test.support.case_reader import FakeCaseReader
from test.support.connector_ports import surplus_members
from vultron.adapters.connectors.base import (
    CONNECTOR_PORTS,
    ConnectorPlugin,
    ports_implemented_by,
)
from vultron.core.ports.case_reader import CaseReader


class _NameOnly:
    name = "name-only"


class _ReaderWithWriteStub(FakeCaseReader):
    def write_case(self, case_id: str) -> None:
        raise NotImplementedError


@pytest.mark.spec("ARCH-05-004")
def test_connector_plugin_requires_only_a_name():
    assert get_protocol_members(ConnectorPlugin) == {"name"}


@pytest.mark.spec("ARCH-05-004")
def test_case_reader_is_a_connector_port():
    assert CaseReader in CONNECTOR_PORTS


@pytest.mark.spec("ARCH-05-004")
def test_a_plugin_with_a_name_and_no_port_implements_none():
    plugin = _NameOnly()
    assert isinstance(plugin, ConnectorPlugin)
    assert ports_implemented_by(plugin) == ()


@pytest.mark.spec("ARCH-05-004")
def test_a_case_reader_plugin_reports_the_case_reader_port():
    assert ports_implemented_by(FakeCaseReader({})) == (CaseReader,)


def test_a_plugin_missing_one_member_of_a_port_does_not_implement_it():
    class _ReadOnlyNoDeclaration:
        name = "partial"

        def read_case(self, case_id: str) -> object:
            raise NotImplementedError

    assert ports_implemented_by(_ReadOnlyNoDeclaration()) == ()


@pytest.mark.spec("ARCH-05-005")
def test_a_plugin_exposing_only_its_ports_has_no_surplus():
    assert surplus_members(FakeCaseReader({})) == set()


@pytest.mark.spec("ARCH-05-005")
def test_a_write_stub_beside_a_read_port_is_surplus():
    assert surplus_members(_ReaderWithWriteStub({})) == {"write_case"}
