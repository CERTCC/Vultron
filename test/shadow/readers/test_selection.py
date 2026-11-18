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

"""The case shadow tool's reader for each source (#6441, #6530, #6642).

The recorded demo cases are read through the Vultron case reader over ledger
files, a running node through the live Vultron case reader, and an outside
system through its own reader.
"""

import pytest

from test.support.case_reader import FakeCaseReader
from vultron.core.ports.case_reader import CaseReader
from vultron.errors import CaseLedgerFileError
from vultron.shadow.readers import (
    CaseSource,
    VultronCaseReader,
    VultronNode,
    VultronNodeCaseReader,
    select_case_reader,
)

_NODE = VultronNode("http://case-actor:7999/api/v2", "case-actor")


def test_the_recordings_are_the_default_source_read_from_ledger_files():
    assert isinstance(select_case_reader(), VultronCaseReader)
    assert isinstance(
        select_case_reader(CaseSource.RECORDINGS), VultronCaseReader
    )


def test_the_outside_source_is_read_through_its_reader():
    outside = FakeCaseReader({})
    reader = select_case_reader(CaseSource.OUTSIDE, outside=outside)
    assert reader is outside
    assert isinstance(reader, CaseReader)


def test_the_recordings_reader_keeps_to_the_ledger_root(tmp_path):
    reader = select_case_reader(ledger_root=tmp_path)
    with pytest.raises(CaseLedgerFileError, match="outside the ledger"):
        reader.read_case(str(tmp_path.parent / "other.jsonl"))


def test_the_node_source_is_read_through_the_live_reader():
    reader = select_case_reader(CaseSource.NODE, node=_NODE)
    assert isinstance(reader, VultronNodeCaseReader)
    assert reader.node_url == _NODE.url


def test_each_source_reads_through_its_own_reader_whatever_else_is_given():
    outside = FakeCaseReader({})
    assert isinstance(
        select_case_reader(CaseSource.RECORDINGS, outside=outside, node=_NODE),
        VultronCaseReader,
    )
    assert isinstance(
        select_case_reader(CaseSource.NODE, outside=outside, node=_NODE),
        VultronNodeCaseReader,
    )
    assert (
        select_case_reader(CaseSource.OUTSIDE, outside=outside, node=_NODE)
        is outside
    )


@pytest.mark.parametrize("source", [CaseSource.OUTSIDE, CaseSource.NODE])
def test_a_source_without_what_it_reads_is_refused(source):
    with pytest.raises(ValueError, match="needs"):
        select_case_reader(source)
