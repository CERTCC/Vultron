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
"""The ``received/embargo/`` package keeps its split shape (#4105).

The flat ``received/embargo.py`` grew past the CS-18 cap and was split into
one module per verb family.  These tests pin the two halves of that split:
every submodule stays under the cap (CS-18-001, CS-18-002), and every name
the flat module exported still imports from the package (CS-18-003).
"""

import importlib
from pathlib import Path

import pytest

import vultron.core.use_cases.received.embargo as embargo_pkg

_CAP = 500

_SUBMODULES = (
    "accept",
    "announce",
    "create_add_remove",
    "invite",
    "owner_decision",
    "reject",
)

#: Every public name the flat module exported before the split, plus the
#: one private helper a test imports by that path.
_FORMER_EXPORTS = (
    "AcceptInviteToEmbargoOnCaseReceivedUseCase",
    "AnnounceEmbargoEventToCaseReceivedUseCase",
    "CreateEmbargoEventReceivedUseCase",
    "InviteToEmbargoOnCaseReceivedUseCase",
    "RejectInviteToEmbargoOnCaseReceivedUseCase",
    "RemoveEmbargoEventFromCaseReceivedUseCase",
    "resolve_invitee_id",
    "resolve_proposer_id",
)


@pytest.mark.spec("CS-18-001", "CS-18-002")
@pytest.mark.parametrize("name", _SUBMODULES)
def test_submodule_stays_under_the_module_cap(name: str) -> None:
    module = importlib.import_module(f"{embargo_pkg.__name__}.{name}")
    assert module.__file__ is not None
    lines = len(Path(module.__file__).read_text(encoding="utf-8").splitlines())
    assert lines <= _CAP, (
        f"{name}.py is {lines} lines; split it again (CS-18-002)"
    )


@pytest.mark.spec("CS-18-003")
@pytest.mark.parametrize("name", _FORMER_EXPORTS)
def test_former_flat_module_name_still_imports_from_the_package(
    name: str,
) -> None:
    assert name in embargo_pkg.__all__
    exported = getattr(embargo_pkg, name)
    # The re-export is the defining object, not a copy (CS-15-001).
    assert exported.__module__.startswith(f"{embargo_pkg.__name__}.")
