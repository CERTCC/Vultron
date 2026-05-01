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
Unit tests for vultron.wire.as2.factories.errors.

Spec coverage:
- AF-04-001: Factory functions MUST wrap ValidationError in
  VultronActivityConstructionError.
- AF-04-002: VultronActivityConstructionError MUST be defined in
  factories/errors.py and re-exported from factories/__init__.py.
"""

import pytest

from vultron.errors import VultronError
from vultron.wire.as2.factories import VultronActivityConstructionError
from vultron.wire.as2.factories.errors import (
    VultronActivityConstructionError as DirectImport,
)


def test_construction_error_is_vultron_error():
    """VultronActivityConstructionError must inherit from VultronError (AF-04-002)."""
    assert issubclass(VultronActivityConstructionError, VultronError)


def test_construction_error_reexported_from_package():
    """VultronActivityConstructionError must be importable from factories __init__ (AF-04-002)."""
    assert VultronActivityConstructionError is DirectImport


def test_construction_error_can_be_raised_with_cause():
    """VultronActivityConstructionError supports chained __cause__ (AF-04-001)."""
    original = ValueError("bad field")
    try:
        raise VultronActivityConstructionError("factory failed") from original
    except VultronActivityConstructionError as exc:
        assert str(exc) == "factory failed"
        assert exc.__cause__ is original


def test_construction_error_is_catchable_as_vultron_error():
    """VultronActivityConstructionError is catchable as VultronError."""
    with pytest.raises(VultronError):
        raise VultronActivityConstructionError("test")
