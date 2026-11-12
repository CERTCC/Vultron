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

"""The state-string parsers accept exactly the ``CS`` names (#6328).

They validate against the authoritative ``CS`` enum, not the legacy
``case_states.validations`` rules, and refuse a string that names no state
with the ``StateValidationError`` the legacy decorator raised for every
string it refused.  Two inputs changed: a wildcard pattern such as ``V.d...``
passed the legacy check and then raised ``KeyError``, and a non-string raised
``TypeError``; both now raise ``StateValidationError`` too.  The legacy model
is the oracle for which strings are states (ADR-0060), and the success tests
spell each state's parts from its name, independently of the ``CS`` member
values the parsers now read.
"""

from itertools import product

import pytest

from vultron.core.case_states.validations import valid_states
from vultron.core.states.cs import parsing
from vultron.core.states.cs.states import CS, CS_d, CS_pxa, CS_vf
from vultron.errors import StateValidationError

_PARSERS = [
    parsing.vfd,
    parsing.pxa,
    parsing.state_string_to_enums,
    parsing.state_string_to_enum2,
]

#: Every upper/lower-case spelling of the six events, plus wildcard patterns.
_SPELLINGS = ["".join(p) for p in product("vV", "fF", "dD", "pP", "xX", "aA")]

_NOT_STATES = [
    "vFdpxa",  # fix ready before the vendor is aware
    "vfDpxa",  # fix deployed before it is ready
    "VfDPXA",
    "V.d...",  # a pattern, not a state
    "......",
    "vfdpx",  # too short
    "vfdpxaa",  # too long
    "xpdfva",  # events out of order
    "VFDPXa ",
    "",
    None,
    42,
    CS.vfdpxa,  # a member, not a state string
]


def test_cs_state_names_exactly_the_legacy_valid_states():
    accepted = set()
    for spelling in _SPELLINGS:
        try:
            parsing.cs_state(spelling)
        except StateValidationError:
            continue
        accepted.add(spelling)
    assert accepted == set(valid_states())


@pytest.mark.spec("CSB-17-001")
@pytest.mark.parametrize("member", list(CS), ids=lambda m: m.name)
def test_cs_state_returns_the_named_member(member):
    assert parsing.cs_state(member.name) is member


@pytest.mark.spec("CSB-17-001")
@pytest.mark.parametrize("parser", _PARSERS, ids=lambda f: f.__name__)
@pytest.mark.parametrize("bad", _NOT_STATES, ids=repr)
def test_every_parser_refuses_a_string_naming_no_state(parser, bad):
    with pytest.raises(StateValidationError):
        parser(bad)


def _spelled_parts(name: str) -> tuple[CS_vf, CS_d, CS_pxa]:
    """The parts a state name spells, read from its letters alone."""
    return (CS_vf[name[:2]], CS_d[name[2]], CS_pxa[name[3:]])


_NAMES = [member.name for member in CS]


@pytest.mark.parametrize("name", _NAMES)
def test_state_string_to_enums_returns_the_spelled_parts(name):
    assert parsing.state_string_to_enums(name) == _spelled_parts(name)


@pytest.mark.parametrize("name", _NAMES)
def test_vfd_returns_the_spelled_vf_and_d_parts(name):
    assert parsing.vfd(name) == _spelled_parts(name)[:2]


@pytest.mark.parametrize("name", _NAMES)
def test_pxa_returns_the_spelled_pxa_value(name):
    assert parsing.pxa(name) == _spelled_parts(name)[2].value


@pytest.mark.parametrize("member", list(CS), ids=lambda m: m.name)
def test_state_string_to_enum2_spells_the_state(member):
    parts = parsing.state_string_to_enum2(member.name)
    assert "".join(str(p) for p in parts) == member.name
