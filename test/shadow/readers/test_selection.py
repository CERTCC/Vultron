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

"""The case shadow's reader choice: Vultron's unless an outside one is set (#6441)."""

import pytest

from test.support.case_reader import FakeCaseReader
from vultron.core.ports.case_reader import CaseReader
from vultron.errors import CaseLedgerFileError
from vultron.shadow.readers import VultronCaseReader, select_case_reader


def test_with_no_outside_reader_the_run_reads_vultron_ledger_files():
    reader = select_case_reader()
    assert isinstance(reader, VultronCaseReader)
    assert isinstance(select_case_reader(None), VultronCaseReader)


def test_a_configured_outside_reader_is_the_one_used():
    outside = FakeCaseReader({})
    reader = select_case_reader(outside)
    assert reader is outside
    assert isinstance(reader, CaseReader)


def test_the_default_reader_keeps_to_the_ledger_root(tmp_path):
    reader = select_case_reader(ledger_root=tmp_path)
    with pytest.raises(CaseLedgerFileError, match="outside the ledger"):
        reader.read_case(str(tmp_path.parent / "other.jsonl"))
