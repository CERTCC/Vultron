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

"""Tests for the fresh-interpreter import probe.

The guards that use it only ever assert that nothing is loaded, so a probe
that stopped seeing loads would pass them silently.  These tests check that
it reports a package an import does load, indirect loads included.
"""

import pytest

from test.support.fresh_imports import loaded_under


def test_reports_a_package_the_import_loads():
    assert loaded_under(["csv"], ["csv"]) == ["csv"]


def test_reports_an_indirect_load():
    """The legacy validations module imports ``vultron.errors`` in turn."""
    loaded = loaded_under(
        ["vultron.core.case_states.validations"], ["vultron.errors"]
    )
    assert loaded == ["vultron.errors"]


def test_does_not_match_a_name_that_only_shares_a_prefix():
    assert loaded_under(["csv"], ["cs"]) == []


@pytest.mark.parametrize(
    ("imports", "packages"), [([], ["json"]), (["json"], [])]
)
def test_refuses_an_empty_question(imports, packages):
    with pytest.raises(ValueError, match="at least one"):
        loaded_under(imports, packages)
